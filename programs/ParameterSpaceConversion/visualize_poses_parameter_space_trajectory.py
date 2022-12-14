import glob
import json
import os
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.preprocessing import MinMaxScaler

POSE_BODY_25_PAIRS_RENDER_GPU = \
    [1, 8, 1, 2, 1, 5, 2, 3, 3, 4, 5, 6, 6, 7, 8, 9, 9, 10, 10, 11,
     8, 12, 12, 13, 13, 14, 1, 0, 0, 15, 15, 17, 0, 16, 16, 18, 14,
     19, 19, 20, 14, 21, 11, 22, 22, 23, 11, 24]

POSE_BODY_25_COLORS_RENDER_GPU = \
    [255, 0, 85,
     255, 0, 0,
     255, 85, 0,
     255, 170, 0,
     255, 255, 0,
     170, 255, 0,
     85, 255, 0,
     0, 255, 0,
     255, 0, 0,
     0, 255, 85,
     0, 255, 170,
     0, 255, 255,
     0, 170, 255,
     0, 85, 255,
     0, 0, 255,
     255, 0, 170,
     170, 0, 255,
     255, 0, 255,
     85, 0, 255,
     0, 0, 255,
     0, 0, 255,
     0, 0, 255,
     0, 255, 255,
     0, 255, 255,
     0, 255, 255]


def main():
    parser = argparse.ArgumentParser(
        description="Convert poses to Parameter Space to Human Action Recognition"
    )

    parser.add_argument("--poses_base_dir", type=str,
                        default='/home/murilo/dataset/KTH',
                        help="Name of directory where input points are located.")

    parser.add_argument("--input_dir", type=str,
                        default='2DPoses',
                        help="Name of directory to output computed features.")

    parser.add_argument("--output_images_dir", type=str,
                        default='2DPoses_SpaceParam_Images',
                        help="Name of directory to output Parameter Space images.")

    parser.add_argument("--image_height", type=int,
                        default='240',
                        help="(Frame Size)Image height to compute max distance in Parameter Space.")

    parser.add_argument("--image_width", type=int,
                        default='320',
                        help="(Frame Size)Image width to compute max distance in Parameter Space.")

    parser.add_argument("--draw_body_ids", type=int,
                        default='1',
                        help="Whether draw body joint ids in image with points in Parameter Space.")

    parser.add_argument("--number_frames", type=int,
                        default=20,
                        help="Number of frames to extract features.")

    parser.add_argument("--stride", type=int,
                        default=1,
                        help="Stride to compute features from the frames.")

    args = parser.parse_args()
    convert_parameter_space(args)


def convert_parameter_space(args):
    # here compute image diagonal = max distance in Parameter Space
    max_distance = int(((args.image_height ** 2) + (args.image_width ** 2)) ** (1 / 2))
    print(max_distance)

    thetas = np.linspace(-np.pi / 2, np.pi / 2, 180)

    #poses_dir = os.path.join(args.poses_base_dir, args.input_dir)

    points = 14
    for root, directories, filenames in os.walk(os.path.join(args.poses_base_dir, args.input_dir)):
        for directory in directories:
            video_dir = os.path.join(root, directory)
            print(video_dir)
            frames = sorted(glob.glob(video_dir + '/*.json'))
            if len(frames) > 0:
                for x in range(0, len(frames), args.stride):
                    if x + args.number_frames < len(frames):
                        img_parameter_traj = {}
                        draw = {}
                        for u in range(14):
                            img_parameter_traj[u] = Image.new('RGB', (180 + 20, int(max_distance)), color='black')
                            draw[u] = ImageDraw.Draw(img_parameter_traj[u])

                        prev_points_parameter_space = None
                        for y in range(x, x + args.number_frames + 1):
                            body_parts = read_body_parts_file(frames[y])
                            if len(body_parts) > 0:
                                # compute parameter space points and draw image with points
                                points_parameter_space = \
                                    compute_parameter_space(body_parts, max_distance, thetas)

                                if prev_points_parameter_space is None:
                                    prev_points_parameter_space = points_parameter_space
                                else:
                                    for a in range(len(points_parameter_space)):
                                    #for a in [2,3,4,5]:
                                    #if 1 == 1:
                                        #a = 4
                                        x1 = prev_points_parameter_space[a][0]
                                        y1 = prev_points_parameter_space[a][1]
                                        x2 = points_parameter_space[a][0]
                                        y2 = points_parameter_space[a][1]
                                        color_id = points_parameter_space[a][2]
                                        shape = (x1, y1, x2, y2)
                                        draw[a].line(shape, fill=get_color(color_id))
                                        e_size = 2
                                        draw[a].ellipse((x1 - e_size, abs(y1) - e_size, x1 + e_size, abs(y1) + e_size),
                                                     fill=get_color(color_id))
                                        draw[a].ellipse((x2 - e_size, abs(y2) - e_size, x2 + e_size, abs(y2) + e_size),
                                                     fill=get_color(color_id))
                                    prev_points_parameter_space = points_parameter_space

                        images_dir = video_dir.replace(args.input_dir, args.output_images_dir)
                        #images_dir, video_name = os.path.split(images_dir)
                        if not os.path.exists(images_dir):
                            os.makedirs(images_dir)
                        for i in range(14):
                            file = os.path.join(images_dir, str(i) + '_'+ str(x) + '_trajectories.png')
                            img_parameter_traj[i].save(file)


def read_body_parts_file(key_points_file):
    body_parts_int = {}

    # Read json pose points
    with open(key_points_file) as f:
        data = json.load(f)

    body_parts = data['part_candidates'][0]
    if len(body_parts) > 0:

        for key, value in body_parts.items():
            body_parts_int[int(key)] = [item for item in value]

    return body_parts_int


def compute_parameter_space(body_parts, max_distance, thetas, draw_body_ids=True):
    # Create image degrees x max_distance
    points_parameter_space = {}
    for i in range(0, 14, 1):
        degree = degree_disc = theta = rho1 = rho2 = 0
        x1, y1, x2, y2, color_id, id1, id2 = return_body_points_coord(i, body_parts)
        if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:
            #print(i)
            # print('x1:\t%i\ty1:\t%i\t\tx2:\t%i\ty2:\t%i' % (x1, y1, x2, y2))
            if y1 - y2 != 0:
                theta = np.arctan((x2 - x1) / (y1 - y2))
            else:
                theta = 0

            # here convert theta from radians to degrees
            degree = round(theta * (180 / np.pi))

            # here find theta in thetas discrete list (only for image plot)
            degree_disc = min(range(len(thetas)), key=lambda x: abs(thetas[x] - theta))
            # position_min_degree = min(thetas, key=lambda x: abs(x - theta))

            # compute rho from theta
            rho1 = x1 * np.cos(theta) + y1 * np.sin(theta)
            rho2 = x2 * np.cos(theta) + y2 * np.sin(theta)
            #print(rho1, rho2)

            #print(int(rho1), int(degree), x1, y1)
        points_parameter_space[i] = (degree_disc, rho1, color_id)
        # points_hough[i] = (degree, degree_disc, theta, int(rho))

    return points_parameter_space


def return_body_points_coord(i, body_parts):
    x1 = y1 = x2 = y2 = x = color_id = id1 = id2 = 0
    if i == 0:  # 1 => 0 Neck
        x = 13
    elif i == 1:  # 1 => 8 Upper body
        x = 0
    elif i == 2:  # 2 => 3 Right Arm
        x = 3
    elif i == 3:  # 3 => 4 Right Forearm
        x = 4
    elif i == 4:  # 5 => 6 Left Arm
        x = 5
    elif i == 5:  # 6 => 7 Left Forearm
        x = 6
    elif i == 6:  # 9 => 10 Right Thigh
        x = 8
    elif i == 7:  # 10 => 11 Right Leg
        x = 9
    elif i == 8:  # 12 => 13 Left Thigh
        x = 11
    elif i == 9:  # 13 => 14 Left Leg
        x = 12
    elif i == 10:  # 8 => 9 Right Hip
        x = 7
    elif i == 11:  # 8 => 12 Left Hip
        x = 10
    elif i == 12:  # 1 => 2 Right Shoulder
        x = 1
    elif i == 13:  # 1 => 5 Left Shoulder
        x = 2

    x = x * 2
    if (len(body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x]]) > 0 and len(
            body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x + 1]]) > 0):
        x1, y1 = get_max_prob(body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x]])
        x2, y2 = get_max_prob(body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x + 1]])
        color_id = POSE_BODY_25_PAIRS_RENDER_GPU[x + 1] * 3
        id1 = POSE_BODY_25_PAIRS_RENDER_GPU[x]
        id2 = POSE_BODY_25_PAIRS_RENDER_GPU[x + 1]

    return x1, y1, x2, y2, color_id, id1, id2


def draw_body(body_parts, height, width):
    img = Image.new('RGB', (width, height), color='black')
    draw = ImageDraw.Draw(img)

    for k in sorted(body_parts):
        if len(body_parts[k]) > 0:
            x, y = get_max_prob(body_parts[k])
            draw.point((x, y), fill=get_color(k * 3))

    ctd = 0
    for x in range(0, len(POSE_BODY_25_PAIRS_RENDER_GPU), 2):
        print(x, x + 1)
        print(POSE_BODY_25_PAIRS_RENDER_GPU[x], POSE_BODY_25_PAIRS_RENDER_GPU[x + 1])
        print(body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x]], body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x + 1]])
        print('\n')
        if (len(body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x]]) > 0 and len(
                body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x + 1]]) > 0):
            x1, y1 = get_max_prob(body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x]])
            x2, y2 = get_max_prob(body_parts[POSE_BODY_25_PAIRS_RENDER_GPU[x + 1]])
            draw.line((x1, y1, x2, y2), fill=get_color(POSE_BODY_25_PAIRS_RENDER_GPU[x + 1] * 3), width=1)
            ctd = ctd + 1
    print(ctd)

    img.show()
    img.save('pil_red.png')


def get_max_prob(body_part):
    m = 0
    x = 0
    y = 0
    for p in range(0, len(body_part), 3):
        if body_part[p + 2] > m:
            m = float(body_part[p + 2])
            x = int(body_part[p])
            y = int(body_part[p + 1])

    return x, y


def get_color(k):
    return POSE_BODY_25_COLORS_RENDER_GPU[k], \
           POSE_BODY_25_COLORS_RENDER_GPU[k + 1], \
           POSE_BODY_25_COLORS_RENDER_GPU[k + 2]


if __name__ == "__main__":
    main()
