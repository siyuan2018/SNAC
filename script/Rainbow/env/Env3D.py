from collections import deque

import cv2
import gym
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import torch

from common.utils import save_plot


class Env3DStatic(gym.Env):
    def __init__(self, args):
        self.plan_width = 20
        self.plan_height = 20
        self.plan_length = 10  # Z Axis
        self.z = 6

        self.plan_choose = (args.plan_choose if args.plan_choose is not None else 0)

        self.environment_memory = None
        self.count_brick = None
        self.brick_memory = None
        self.HALF_WINDOW_SIZE = 3
        self.environment_width = self.plan_width + 2 * self.HALF_WINDOW_SIZE
        self.environment_height = self.plan_height + 2 * self.HALF_WINDOW_SIZE
        self.environment_length = self.plan_length + 2 * self.HALF_WINDOW_SIZE

        self.start = None
        self.position_memory = None
        self.observation = None
        self.count_step = 0
        self.total_step = 1300
        self.plan, self.total_brick = self.create_plan()
        self.input_plan = None

        self.check = []
        self.action_dim = 8
        self.state_dim = (self.HALF_WINDOW_SIZE * 2 + 1) ** 2 + 2
        self.blank_size = 2  # use 0, 2, 4
        self.window = args.history_length
        self.uniform_step = args.uniform_step
        self.step_size = 1

        self.features = 51 - 1

    def get_features(self):
        return self.features

    def action_space(self):
        return self.action_dim

    def create_plan(self):
        out_radius = 7
        if self.plan_choose == 0:
            in_radius = 0
        elif self.plan_choose == 1:
            out_radius = 8
            in_radius = 7

        plan = np.zeros((self.environment_height, self.environment_width))
        a = np.array([12.5, 12.5])
        circle = patches.CirclePolygon(a, out_radius)
        circle2 = patches.CirclePolygon(a, in_radius)
        for i in range(len(plan)):
            for j in range(len(plan[0])):
                a = np.array([i, j])
                if circle.contains_point(a) and not circle2.contains_point(a):
                    plan[i][j] = 1

            total_area = sum(sum(plan))
        plan = plan * self.z
        total_area = total_area * self.z
        return plan, total_area

    def observation_(self, position):
        observation = self.environment_memory[
                      position[0] - self.HALF_WINDOW_SIZE : position[0] + self.HALF_WINDOW_SIZE + 1,
                      position[1] - self.HALF_WINDOW_SIZE : position[1] + self.HALF_WINDOW_SIZE + 1]

        return observation.flatten().reshape(1, -1)

    def clip_position(self, position):
        if position[0] <= self.HALF_WINDOW_SIZE:
            position[0] = self.HALF_WINDOW_SIZE
        if position[1] <= self.HALF_WINDOW_SIZE:
            position[1] = self.HALF_WINDOW_SIZE
        if position[0] >= self.plan_width+self.HALF_WINDOW_SIZE - 1:
            position[0] = self.plan_width+self.HALF_WINDOW_SIZE - 1
        if position[1] >= self.plan_width+self.HALF_WINDOW_SIZE - 1:
            position[1] = self.plan_width+self.HALF_WINDOW_SIZE -1
        return position

    def reset(self):
        self.plan, self.total_brick = self.create_plan()

        self.input_plan = self.plan[
                          self.HALF_WINDOW_SIZE : self.HALF_WINDOW_SIZE + self.plan_height,
                          self.HALF_WINDOW_SIZE : self.HALF_WINDOW_SIZE + self.plan_width]
        self.environment_memory = np.zeros((self.environment_height, self.environment_width))
        self.environment_memory[:, :self.HALF_WINDOW_SIZE] = -1
        self.environment_memory[:, -self.HALF_WINDOW_SIZE:] = -1
        self.environment_memory[:self.HALF_WINDOW_SIZE, :] = -1
        self.environment_memory[-self.HALF_WINDOW_SIZE:, :] = -1

        self.check = []
        self.count_brick = 0
        self.step_size = 1

        self.position_memory = []
        self.observation = None
        self.count_step = 0
        initial_position = [self.HALF_WINDOW_SIZE, self.HALF_WINDOW_SIZE]

        self.position_memory.append(initial_position)

        return np.hstack(
            (self.observation_(initial_position),
             np.array([[self.count_brick]]),
             np.array([[self.count_step]])))

    def check_sur(self, position):
        # 0 left, 1 right, 2 up, 3 down
        check = [0, 0, 0, 0, 0, 0, 0, 0]

        observation = [self.environment_memory[position[0], position[1] - 1],
                       self.environment_memory[position[0], position[1] + 1],
                       self.environment_memory[position[0] + 1, position[1]],
                       self.environment_memory[position[0] - 1, position[1]]]
        for i in range(len(observation)):
            if observation[i] == -1:
                check[i] = 1
                check[i + 4] = 1
            elif observation[i] > 0:
                check[i] = 1
        return check

    def move_step(self, position, action, step_size):
        move = 0
        if action == 0:
            for i in range(step_size):
                observation = self.environment_memory[position[0], position[1] - i - 1]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 1:
            for i in range(step_size):
                observation = self.environment_memory[position[0], position[1] + i + 1]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 2:
            for i in range(step_size):
                observation = self.environment_memory[position[0] + i + 1, position[1]]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 3:
            for i in range(step_size):
                observation = self.environment_memory[position[0] - i - 1, position[1]]
                if observation == 0:
                    move += 1
                else:
                    break
        return move

    def step(self, action):
        if self.uniform_step:
            self.step_size = 1
        else:
            self.step_size = np.random.randint(1, 4)

        self.count_step += 1
        self.check = self.check_sur(self.position_memory[-1])

        # print("Action: ", action)
        # moving: 0 left, 1 right, 2 up, 3 down
        if action == 0 and self.check[0] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0], self.position_memory[-1][1] - step_size]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 1 and self.check[1] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0], self.position_memory[-1][1] + step_size]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 2 and self.check[2] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0] + step_size, self.position_memory[-1][1]]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 3 and self.check[3] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0] - step_size, self.position_memory[-1][1]]
            position = self.clip_position(position)
            self.position_memory.append(position)

        # building brick: 4 left_brick, 5 right_brick, 6 up_brick, 7 down_brick
        elif action > 3:
            build_brick = True
            position = self.position_memory[-1]
            self.position_memory.append(position)
            if action == 4 and self.check[4] == 0:
                self.count_brick += 1
                brick_target = [position[0], position[1] - 1]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 5 and self.check[5] == 0:
                self.count_brick += 1
                brick_target = [position[0], position[1] + 1]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 6 and self.check[6] == 0:
                self.count_brick += 1
                brick_target = [position[0] + 1, position[1]]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 7 and self.check[7] == 0:
                self.count_brick += 1
                brick_target = [position[0] - 1, position[1]]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            else:
                build_brick = False

            # print("Brick Count: ", self.count_brick, "\t/\tTotal Bricks: ", self.total_brick)
            done = bool(self.count_brick > self.total_brick) or self.check[0:4] == [1, 1, 1, 1]
            if done:
                observation = np.hstack(
                    (self.observation_(position),
                     np.array([[self.count_brick]]),
                     np.array([[self.count_step]])))

                reward = 0.0
                return observation, reward, done
            else:
                if build_brick:
                    reward = self.reward_check(brick_target)
                    observation = np.hstack(
                        (self.observation_(position),
                         np.array([[self.count_brick]]),
                         np.array([[self.count_step]])))
                    
                    return observation, reward, done
        else:
            # illegal_move = useless_move!!
            position = self.position_memory[-1]

        # print("Step Count: ", self.count_step, "\t/\tTotal Steps: ", self.total_step)
        done = bool(self.count_step > self.total_step) or self.check[0:4] == [1, 1, 1, 1]
        observation = np.hstack(
            (self.observation_(position),
             np.array([[self.count_brick]]),
             np.array([[self.count_step]])))
        reward = 0.0
        return observation, reward, done

    def reward_check(self, position):
        if self.environment_memory[position[0], position[1]] > self.plan[position[0], position[1]]:
            reward = -0.01
        elif self.environment_memory[position[0], position[1]] == self.plan[position[0], position[1]]:
            reward = 10.0
        else:
            reward = 1.0
        return reward

    def plot_3d(self, plan, Env=False):
        if Env:
            z_max = max(max(row) for row in plan)
        else:
            z_max = 1
        X, Y, Z = [], [], []
        for i in range(int(z_max)):
            for j in range(len(plan)):
                for k in range(len(plan[0])):
                    if self.environment_length > plan[j][k] > 0:
                        X.append(k)
                        Y.append(j)
                        Z.append(plan[j][k])
            plan = plan - 1.0
        return X, Y, Z

    def render(self, ax, ax2, args, environment_memory, plan, highest_iou, count_step,
               count_brick, datetime, iou_min=None, iou_average=None, iter_times=10):
        ax.clear()
        ax2.clear()

        ax.set_xlim(0, self.plan_width)
        ax.set_ylim(0, self.plan_height)
        ax.set_zlim(0, self.plan_length)

        ax2.set_xlabel('X-axis')
        ax2.set_xlim(-1, self.plan_width)
        ax2.set_ylabel('Y-axis')
        ax2.set_ylim(-1, self.plan_height)

        plan = self.plan[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
               self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        plan_2d = np.zeros((self.plan_height, self.plan_width))
        IOU = self._iou()
        # if best_env.any():
        #     env_memory = best_env[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height, \
        #                  self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]
        #     IOU = best_iou
        #     step = best_step
        #     brick = best_brick
        #     best_posi = position_memo
        # else:
        env_memory = self.environment_memory[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height, \
                     self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]
        step = self.count_step
        brick = self.count_brick
        best_posi = self.position_memory[-1]

        env_memory_2d = np.zeros((self.plan_height, self.plan_width))
        for i in range(self.plan_height):
            for j in range(self.plan_width):
                if plan[i][j] > 0:
                    plan_2d[i][j] = 1
                if env_memory[i][j] > 0:
                    env_memory_2d[i][j] = 1

        background = np.zeros((self.plan_height, self.plan_width))
        img = np.stack((env_memory_2d, plan_2d, background), axis=2)

        # plot_plan_surface
        X, Y, Z = self.plot_3d(plan, Env=False)

        ax.scatter(X, Y, Z, marker='s', s=40, color='r', edgecolor="k",alpha=1)

        x1, y1, z1 = self.plot_3d(env_memory, Env=True)

        width = depth = 1
        height = np.zeros_like(z1)
        if x1:
            ax.bar3d(x1, y1, height, width, depth, z1, color='b', shade=True,alpha=0.15, edgecolor="k")

        ax.scatter(best_posi[1] - self.HALF_WINDOW_SIZE + 0.5,
                    best_posi[0] - self.HALF_WINDOW_SIZE + 0.5, zs=0, marker="*", color='b', s=50)


        if iou_min is None:
            iou_min = IOU
        if iou_average is None:
            iou_average = IOU
        ax.title.set_text('step=%d,used_paint=%d,IOU=%.3f' % (step, brick, IOU))
        ax2.text(0, 20, 'Iou_min_iter_%d = %.3f' % (iter_times, iou_min), color='r', fontsize=12)
        ax2.text(0, 21.2, 'Iou_average_iter_%d = %.3f' % (iter_times, iou_average), color='b', fontsize=12)

        ax2.axis('off')
        plt.imshow(img)
        ax2.plot(best_posi[1] - self.HALF_WINDOW_SIZE,
                  best_posi[0] - self.HALF_WINDOW_SIZE, '*', color='b')
        save_plot(args, datetime)
        plt.draw()

    def _iou(self):
        plan = self.plan[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
               self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        env_memory = self.environment_memory[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
                     self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        env_memory_3d = np.zeros((self.plan_height, self.plan_width))
        for i in range(self.plan_height):
            for j in range(self.plan_width):
                if env_memory[i][j] > plan[i][j]:
                    env_memory_3d[i][j] = plan[i][j]
                else:
                    env_memory_3d[i][j] = env_memory[i][j]
        plan_area = self.total_brick
        env_area = self.count_brick
        cross_area = sum(map(sum, env_memory_3d))
        iou = cross_area / (plan_area + env_area - cross_area)
        return iou


class Env3DDynamic(gym.Env):
    def __init__(self, args):
        self.step_size = 1

        self.plan_width = 20  # X Axis
        self.plan_height = 20  # Y Axis
        self.plan_length = 10  # Z Axis
        self.z = 6

        self.plan_choose = (args.plan_choose if args.plan_choose is not None else 0)

        self.environment_memory = None
        self.count_brick = None
        self.brick_memory = None
        self.HALF_WINDOW_SIZE = 3
        self.environment_width = self.plan_width + 2 * self.HALF_WINDOW_SIZE
        self.environment_height = self.plan_height + 2 * self.HALF_WINDOW_SIZE
        self.environment_length = self.plan_length + 2 * self.HALF_WINDOW_SIZE

        self.start = None
        self.position_memory = None
        self.observation = None
        self.count_step = 0
        self.total_step = 1000
        self.plan, self.total_brick = self.create_plan()
        self.input_plan = None

        self.check = []
        self.action_dim = 8
        self.state_dim = (self.HALF_WINDOW_SIZE * 2 + 1) ** 2 + 2
        self.blank_size = 2  # use 0, 2, 4
        self.window = args.history_length
        self.uniform_step = args.uniform_step

        self.features = 51 - 1

    def get_features(self):
        return self.features

    def action_space(self):
        return self.action_dim

    def create_plan(self):
        if not(self.plan_choose == 1 or self.plan_choose == 0 ):
            raise ValueError(' 0: Dense triangle, 1: Sparse triangle')

        plan = np.zeros((self.environment_height, self.environment_width))
        area_min = [50,20]
        area_max = 110
        total_area = 0
        i = 0
        while total_area <= area_min[self.plan_choose] or total_area>=area_max:
            i += 1
            x = np.random.randint(0, self.plan_width, size=3)
            y = np.random.randint(0, self.plan_height, size=3)

            img_rgb = np.ones((self.plan_height, self.plan_width, 3), np.uint8) * 255
            vertices = np.array([[x[0], y[0]], [x[1], y[1]], [x[2], y[2]]], np.int32)
            pts = vertices.reshape((-1, 1, 2))
            cv2.polylines(img_rgb, [pts], isClosed=True, color=(0, 0, 0))
            if self.plan_choose == 0:
                cv2.fillPoly(img_rgb, [pts], color=(0, 0, 0))

            plan[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
            self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width] = 1 - img_rgb[:, :, 0] / 255
            total_area = sum(sum(plan))
        plan = plan * self.z
        total_area = total_area * self.z
        return plan, total_area

    def observation_(self, position):
        observation = self.environment_memory[
                      position[0] - self.HALF_WINDOW_SIZE : position[0] + self.HALF_WINDOW_SIZE + 1,
                      position[1] - self.HALF_WINDOW_SIZE : position[1] + self.HALF_WINDOW_SIZE + 1]

        return observation.flatten().reshape(1, -1)

    def clip_position(self, position):
        if position[0] <= self.HALF_WINDOW_SIZE:
            position[0] = self.HALF_WINDOW_SIZE
        if position[1] <= self.HALF_WINDOW_SIZE:
            position[1] = self.HALF_WINDOW_SIZE
        if position[0] >= self.plan_width+self.HALF_WINDOW_SIZE - 1:
            position[0] = self.plan_width+self.HALF_WINDOW_SIZE - 1
        if position[1] >= self.plan_width+self.HALF_WINDOW_SIZE - 1:
            position[1] = self.plan_width+self.HALF_WINDOW_SIZE -1
        return position

    def reset(self):
        self.plan, self.total_brick = self.create_plan()

        self.input_plan = self.plan[
                          self.HALF_WINDOW_SIZE : self.HALF_WINDOW_SIZE + self.plan_height,
                          self.HALF_WINDOW_SIZE : self.HALF_WINDOW_SIZE + self.plan_width]
        self.environment_memory = np.zeros((self.environment_height, self.environment_width))
        self.environment_memory[:, :self.HALF_WINDOW_SIZE] = -1
        self.environment_memory[:, -self.HALF_WINDOW_SIZE:] = -1
        self.environment_memory[:self.HALF_WINDOW_SIZE, :] = -1
        self.environment_memory[-self.HALF_WINDOW_SIZE:, :] = -1

        self.check = []
        self.count_brick = 0
        self.step_size = 1

        self.position_memory = []
        self.observation = None
        self.count_step = 0
        initial_position = [self.HALF_WINDOW_SIZE, self.HALF_WINDOW_SIZE]

        self.position_memory.append(initial_position)
        #
        return np.hstack((self.observation_(initial_position),
                          np.array([[self.count_brick]]),
                          np.array([[self.count_step]]),
                          self.input_plan.reshape(1, -1)))

    def check_sur(self, position):
        # 0 left, 1 right, 2 up, 3 down
        check = [0, 0, 0, 0, 0, 0, 0, 0]

        observation = [self.environment_memory[position[0], position[1] - 1],
                       self.environment_memory[position[0], position[1] + 1],
                       self.environment_memory[position[0] + 1, position[1]],
                       self.environment_memory[position[0] - 1, position[1]]]
        for i in range(len(observation)):
            if observation[i] == -1:
                check[i] = 1
                check[i + 4] = 1
            elif observation[i] > 0:
                check[i] = 1
        return check

    def move_step(self, position, action, step_size):
        move = 0
        if action == 0:
            for i in range(step_size):
                observation = self.environment_memory[position[0], position[1] - i - 1]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 1:
            for i in range(step_size):
                observation = self.environment_memory[position[0], position[1] + i + 1]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 2:
            for i in range(step_size):
                observation = self.environment_memory[position[0] + i + 1, position[1]]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 3:
            for i in range(step_size):
                observation = self.environment_memory[position[0] - i - 1, position[1]]
                if observation == 0:
                    move += 1
                else:
                    break
        return move

    def step(self, action):
        if self.uniform_step:
            self.step_size = 1
        else:
            self.step_size = np.random.randint(1, 4)

        self.count_step += 1
        self.check = self.check_sur(self.position_memory[-1])

        # moving: 0 left, 1 right, 2 up, 3 down
        if action == 0 and self.check[0] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0], self.position_memory[-1][1] - step_size]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 1 and self.check[1] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0], self.position_memory[-1][1] + step_size]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 2 and self.check[2] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0] + step_size, self.position_memory[-1][1]]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 3 and self.check[3] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0] - step_size, self.position_memory[-1][1]]
            position = self.clip_position(position)
            self.position_memory.append(position)

        # building brick: 4 left_brick, 5 right_brick, 6 up_brick, 7 down_brick
        elif action > 3:
            build_brick = True
            position = self.position_memory[-1]
            self.position_memory.append(position)
            if action == 4 and self.check[4] == 0:
                self.count_brick += 1
                brick_target = [position[0], position[1] - 1]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 5 and self.check[5] == 0:
                self.count_brick += 1
                brick_target = [position[0], position[1] + 1]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 6 and self.check[6] == 0:
                self.count_brick += 1
                brick_target = [position[0] + 1, position[1]]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 7 and self.check[7] == 0:
                self.count_brick += 1
                brick_target = [position[0] - 1, position[1]]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            else:
                build_brick = False

            done = bool(self.count_brick > self.total_brick) or self.check[0:4] == [1, 1, 1, 1]
            if done:
                observation = np.hstack((self.observation_(position),
                                         np.array([[self.count_brick]]),
                                         np.array([[self.count_step]]),
                                         self.input_plan.reshape(1, -1)))
                reward = 0.0
                return observation, reward, done
            else:
                if build_brick:
                    reward = self.reward_check(brick_target)
                    observation = np.hstack((self.observation_(position),
                                             np.array([[self.count_brick]]),
                                             np.array([[self.count_step]]),
                                             self.input_plan.reshape(1, -1)))

                    return observation, reward, done
        else:
            # illegal_move = useless_move!!
            position = self.position_memory[-1]

        done = bool(self.count_step > self.total_step) or self.check[0:4] == [1, 1, 1, 1]
        observation = np.hstack((self.observation_(position),
                                 np.array([[self.count_brick]]),
                                 np.array([[self.count_step]]),
                                 self.input_plan.reshape(1, -1)))

        reward = 0.0

        return observation, reward, done

    def reward_check(self, position):
        if self.environment_memory[position[0], position[1]] > self.plan[position[0], position[1]]:
            reward = -0.01
        elif self.environment_memory[position[0], position[1]] == self.plan[position[0], position[1]]:
            reward = 10.0
        else:
            reward = 1.0
        return reward

    def plot_3d(self, plan, Env=False):
        if Env:
            z_max = max(max(row) for row in plan)
        else:
            z_max = 1
        X, Y, Z = [], [], []
        for i in range(int(z_max)):
            for j in range(len(plan)):
                for k in range(len(plan[0])):
                    if self.environment_length > plan[j][k] > 0:
                        X.append(k)
                        Y.append(j)
                        Z.append(plan[j][k])
            plan = plan - 1.0
        return X, Y, Z

    def render(self, ax, ax2, args, environment_memory, plan, highest_iou, count_step,
               count_brick, datetime, iou_min=None, iou_average=None, iter_times=10):
        ax.clear()
        ax2.clear()

        ax.set_xlim(0, self.plan_width)
        ax.set_ylim(0, self.plan_height)
        ax.set_zlim(0, self.plan_length)

        ax2.set_xlabel('X-axis')
        ax2.set_xlim(-1, self.plan_width)
        ax2.set_ylabel('Y-axis')
        ax2.set_ylim(-1, self.plan_height)

        plan = self.plan[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
               self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        plan_2d = np.zeros((self.plan_height, self.plan_width))
        IOU = self._iou()
        # if best_env.any():
        #     env_memory = best_env[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height, \
        #                  self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]
        #     IOU = best_iou
        #     step = best_step
        #     brick = best_brick
        #     best_posi = position_memo
        # else:
        env_memory = self.environment_memory[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height, \
                     self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]
        step = self.count_step
        brick = self.count_brick
        best_posi = self.position_memory[-1]

        env_memory_2d = np.zeros((self.plan_height, self.plan_width))
        for i in range(self.plan_height):
            for j in range(self.plan_width):
                if plan[i][j] > 0:
                    plan_2d[i][j] = 1
                if env_memory[i][j] > 0:
                    env_memory_2d[i][j] = 1

        background = np.zeros((self.plan_height, self.plan_width))
        img = np.stack((env_memory_2d, plan_2d, background), axis=2)

        # plot_plan_surface
        X, Y, Z = self.plot_3d(plan, Env=False)

        ax.scatter(X, Y, Z, marker='s', s=40, color='r', edgecolor="k",alpha=1)

        x1, y1, z1 = self.plot_3d(env_memory, Env=True)

        width = depth = 1
        height = np.zeros_like(z1)
        if x1:
            ax.bar3d(x1, y1, height, width, depth, z1, color='b', shade=True,alpha=0.15, edgecolor="k")

        ax.scatter(best_posi[1] - self.HALF_WINDOW_SIZE + 0.5,
                    best_posi[0] - self.HALF_WINDOW_SIZE + 0.5, zs=0, marker="*", color='b', s=50)


        if iou_min is None:
            iou_min = IOU
        if iou_average is None:
            iou_average = IOU
        ax.title.set_text('step=%d,used_paint=%d,IOU=%.3f' % (step, brick, IOU))
        ax2.text(0, 20, 'Iou_min_iter_%d = %.3f' % (iter_times, iou_min), color='r', fontsize=12)
        ax2.text(0, 21.2, 'Iou_average_iter_%d = %.3f' % (iter_times, iou_average), color='b', fontsize=12)

        ax2.axis('off')
        plt.imshow(img)
        ax2.plot(best_posi[1] - self.HALF_WINDOW_SIZE,
                  best_posi[0] - self.HALF_WINDOW_SIZE, '*', color='b')
        save_plot(args, datetime)
        plt.draw()

    def _iou(self):
        plan = self.plan[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
               self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        env_memory = self.environment_memory[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
                     self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        env_memory_3d = np.zeros((self.plan_height, self.plan_width))
        for i in range(self.plan_height):
            for j in range(self.plan_width):
                if env_memory[i][j] > plan[i][j]:
                    env_memory_3d[i][j] = plan[i][j]
                else:
                    env_memory_3d[i][j] = env_memory[i][j]
        plan_area = self.total_brick
        env_area = self.count_brick
        cross_area = sum(map(sum, env_memory_3d))
        iou = cross_area / (plan_area + env_area - cross_area)
        return iou

class Env3DDynamic_Validation(gym.Env):
    def __init__(self, args):
        self.step_size = 1

        self.plan_width = 20  # X Axis
        self.plan_height = 20  # Y Axis
        self.plan_length = 10  # Z Axis
        self.z = 6

        self.plan_choose = (args.plan_choose if args.plan_choose is not None else 0)

        self.environment_memory = None
        self.count_brick = None
        self.brick_memory = None
        self.HALF_WINDOW_SIZE = 3
        self.environment_width = self.plan_width + 2 * self.HALF_WINDOW_SIZE
        self.environment_height = self.plan_height + 2 * self.HALF_WINDOW_SIZE
        self.environment_length = self.plan_length + 2 * self.HALF_WINDOW_SIZE
        self.tests_set = None

        self.start = None
        self.position_memory = None
        self.observation = None
        self.count_step = 0
        self.total_step = 1000
        self.plan = None
        self.total_brick = None
        self.input_plan = None

        self.check = []
        self.action_dim = 8
        self.state_dim = (self.HALF_WINDOW_SIZE * 2 + 1) ** 2 + 2
        self.blank_size = 2  # use 0, 2, 4
        self.window = args.history_length
        self.uniform_step = args.uniform_step

        self.features = 51 - 1

    def set_tests_set(self, tests_set):
        self.tests_set = tests_set

    def get_features(self):
        return self.features

    def action_space(self):
        return self.action_dim

    def create_plan(self):
        tests = np.array([[[1, 17, 5], [5, 9, 12]],
                            [[11, 7, 18], [17, 3, 16]],
                            [[18, 5, 15], [0, 12, 8]],
                            [[5, 10, 14], [16, 0, 16]],
                            [[4, 14, 19], [3, 17, 10]],
                            [[2, 17, 18], [1, 18, 10]],
                            [[16, 19, 0], [3, 12, 9]],
                            [[11, 18, 5], [13, 14, 1]],
                            [[18, 3, 6], [7, 14, 19]],
                            [[14, 9, 2], [16, 4, 19]]])
        if not (self.plan_choose == 1 or self.plan_choose == 0):
            raise ValueError(' 0: Dense triangle, 1: Sparse triangle')
        if not (0 <= self.tests_set <= 9):
            raise ValueError(' test_set from 0 to 9')

        plan = np.zeros((self.environment_height, self.environment_width))

        x = tests[self.tests_set][0]
        y = tests[self.tests_set][1]

        self.one_hot = [self.plan_choose,self.tests_set]
        img_rgb = np.ones((self.plan_height, self.plan_width, 3), np.uint8) * 255
        vertices = np.array([[x[0], y[0]], [x[1], y[1]], [x[2], y[2]]], np.int32)
        pts = vertices.reshape((-1, 1, 2))
        cv2.polylines(img_rgb, [pts], isClosed=True, color=(0, 0, 0))
        if self.plan_choose == 0:
            cv2.fillPoly(img_rgb, [pts], color=(0, 0, 0))

        plan[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
        self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width] = 1 - img_rgb[:, :, 0] / 255
        total_area = sum(sum(plan))
        plan = plan * self.z
        total_area = total_area * self.z
        return plan, total_area

    def observation_(self, position):
        observation = self.environment_memory[
                      position[0] - self.HALF_WINDOW_SIZE : position[0] + self.HALF_WINDOW_SIZE + 1,
                      position[1] - self.HALF_WINDOW_SIZE : position[1] + self.HALF_WINDOW_SIZE + 1]

        return observation.flatten().reshape(1, -1)

    def clip_position(self, position):
        if position[0] <= self.HALF_WINDOW_SIZE:
            position[0] = self.HALF_WINDOW_SIZE
        if position[1] <= self.HALF_WINDOW_SIZE:
            position[1] = self.HALF_WINDOW_SIZE
        if position[0] >= self.plan_width+self.HALF_WINDOW_SIZE - 1:
            position[0] = self.plan_width+self.HALF_WINDOW_SIZE - 1
        if position[1] >= self.plan_width+self.HALF_WINDOW_SIZE - 1:
            position[1] = self.plan_width+self.HALF_WINDOW_SIZE -1
        return position

    def reset(self):
        self.plan, self.total_brick = self.create_plan()

        self.input_plan = self.plan[
                          self.HALF_WINDOW_SIZE : self.HALF_WINDOW_SIZE + self.plan_height,
                          self.HALF_WINDOW_SIZE : self.HALF_WINDOW_SIZE + self.plan_width]
        self.environment_memory = np.zeros((self.environment_height, self.environment_width))
        self.environment_memory[:, :self.HALF_WINDOW_SIZE] = -1
        self.environment_memory[:, -self.HALF_WINDOW_SIZE:] = -1
        self.environment_memory[:self.HALF_WINDOW_SIZE, :] = -1
        self.environment_memory[-self.HALF_WINDOW_SIZE:, :] = -1

        self.check = []
        self.count_brick = 0
        self.step_size = 1

        self.position_memory = []
        self.observation = None
        self.count_step = 0
        initial_position = [self.HALF_WINDOW_SIZE, self.HALF_WINDOW_SIZE]

        self.position_memory.append(initial_position)

        return np.hstack((self.observation_(initial_position),
                          np.array([[self.count_brick]]),
                          np.array([[self.count_step]]),
                          self.input_plan.reshape(1, -1)))

    def check_sur(self, position):
        # 0 left, 1 right, 2 up, 3 down
        check = [0, 0, 0, 0, 0, 0, 0, 0]

        observation = [self.environment_memory[position[0], position[1] - 1],
                       self.environment_memory[position[0], position[1] + 1],
                       self.environment_memory[position[0] + 1, position[1]],
                       self.environment_memory[position[0] - 1, position[1]]]
        for i in range(len(observation)):
            if observation[i] == -1:
                check[i] = 1
                check[i + 4] = 1
            elif observation[i] > 0:
                check[i] = 1
        return check

    def move_step(self, position, action, step_size):
        move = 0
        if action == 0:
            for i in range(step_size):
                observation = self.environment_memory[position[0], position[1] - i - 1]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 1:
            for i in range(step_size):
                observation = self.environment_memory[position[0], position[1] + i + 1]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 2:
            for i in range(step_size):
                observation = self.environment_memory[position[0] + i + 1, position[1]]
                if observation == 0:
                    move += 1
                else:
                    break
        elif action == 3:
            for i in range(step_size):
                observation = self.environment_memory[position[0] - i - 1, position[1]]
                if observation == 0:
                    move += 1
                else:
                    break
        return move

    def step(self, action):
        if self.uniform_step:
            self.step_size = 1
        else:
            self.step_size = np.random.randint(1, 4)

        self.count_step += 1
        self.check = self.check_sur(self.position_memory[-1])

        # moving: 0 left, 1 right, 2 up, 3 down
        if action == 0 and self.check[0] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0], self.position_memory[-1][1] - step_size]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 1 and self.check[1] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0], self.position_memory[-1][1] + step_size]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 2 and self.check[2] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0] + step_size, self.position_memory[-1][1]]
            position = self.clip_position(position)
            self.position_memory.append(position)
        elif action == 3 and self.check[3] == 0:
            step_size = self.move_step([self.position_memory[-1][0], self.position_memory[-1][1]], action,
                                       self.step_size)
            position = [self.position_memory[-1][0] - step_size, self.position_memory[-1][1]]
            position = self.clip_position(position)
            self.position_memory.append(position)

        # building brick: 4 left_brick, 5 right_brick, 6 up_brick, 7 down_brick
        elif action > 3:
            build_brick = True
            position = self.position_memory[-1]
            self.position_memory.append(position)
            if action == 4 and self.check[4] == 0:
                self.count_brick += 1
                brick_target = [position[0], position[1] - 1]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 5 and self.check[5] == 0:
                self.count_brick += 1
                brick_target = [position[0], position[1] + 1]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 6 and self.check[6] == 0:
                self.count_brick += 1
                brick_target = [position[0] + 1, position[1]]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            elif action == 7 and self.check[7] == 0:
                self.count_brick += 1
                brick_target = [position[0] - 1, position[1]]
                self.environment_memory[brick_target[0], brick_target[1]] += 1.0
            else:
                build_brick = False

            done = bool(self.count_brick > self.total_brick) or self.check[0:4] == [1, 1, 1, 1]
            if done:
                observation = np.hstack((self.observation_(position),
                                  np.array([[self.count_brick]]),
                                  np.array([[self.count_step]]),
                                  self.input_plan.reshape(1, -1)))

                reward = 0.0

                return observation, reward, done
            else:
                if build_brick:
                    reward = self.reward_check(brick_target)
                    observation = np.hstack((self.observation_(position),
                                             np.array([[self.count_brick]]),
                                             np.array([[self.count_step]]),
                                             self.input_plan.reshape(1, -1)))


                    return observation, reward, done
        else:
            # illegal_move = useless_move!!
            position = self.position_memory[-1]

        done = bool(self.count_step > self.total_step) or self.check[0:4] == [1, 1, 1, 1]
        observation = np.hstack((self.observation_(position),
                                 np.array([[self.count_brick]]),
                                 np.array([[self.count_step]]),
                                 self.input_plan.reshape(1, -1)))
        # if self.check[0:4] == [1, 1, 1, 1]:
        #     reward = -5.0
        # else:
        #     reward = 0.0
        reward = 0.0

        return observation, reward, done

    def reward_check(self, position):
        if self.environment_memory[position[0], position[1]] > self.plan[position[0], position[1]]:
            reward = -0.01
        elif self.environment_memory[position[0], position[1]] == self.plan[position[0], position[1]]:
            reward = 10.0
        else:
            reward = 1.0
        return reward

    def plot_3d(self, plan, Env=False):
        if Env:
            z_max = max(max(row) for row in plan)
        else:
            z_max = 1
        X, Y, Z = [], [], []
        for i in range(int(z_max)):
            for j in range(len(plan)):
                for k in range(len(plan[0])):
                    if self.environment_length > plan[j][k] > 0:
                        X.append(k)
                        Y.append(j)
                        Z.append(plan[j][k])
            plan = plan - 1.0
        return X, Y, Z

    def render(self, ax, ax2, args, environment_memory, plan, highest_iou, count_step,
               count_brick, datetime, iou_min=None, iou_average=None, iter_times=10):
        ax.clear()
        ax2.clear()

        ax.set_xlim(0, self.plan_width)
        ax.set_ylim(0, self.plan_height)
        ax.set_zlim(0, self.plan_length)

        ax2.set_xlabel('X-axis')
        ax2.set_xlim(-1, self.plan_width)
        ax2.set_ylabel('Y-axis')
        ax2.set_ylim(-1, self.plan_height)

        plan = self.plan[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
               self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        plan_2d = np.zeros((self.plan_height, self.plan_width))
        IOU = self._iou()
        # if best_env.any():
        #     env_memory = best_env[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height, \
        #                  self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]
        #     IOU = best_iou
        #     step = best_step
        #     brick = best_brick
        #     best_posi = position_memo
        # else:
        env_memory = self.environment_memory[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height, \
                     self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]
        step = self.count_step
        brick = self.count_brick
        best_posi = self.position_memory[-1]

        env_memory_2d = np.zeros((self.plan_height, self.plan_width))
        for i in range(self.plan_height):
            for j in range(self.plan_width):
                if plan[i][j] > 0:
                    plan_2d[i][j] = 1
                if env_memory[i][j] > 0:
                    env_memory_2d[i][j] = 1

        background = np.zeros((self.plan_height, self.plan_width))
        img = np.stack((env_memory_2d, plan_2d, background), axis=2)

        # plot_plan_surface
        X, Y, Z = self.plot_3d(plan, Env=False)

        ax.scatter(X, Y, Z, marker='s', s=40, color='r', edgecolor="k",alpha=1)

        x1, y1, z1 = self.plot_3d(env_memory, Env=True)

        width = depth = 1
        height = np.zeros_like(z1)
        if x1:
            ax.bar3d(x1, y1, height, width, depth, z1, color='b', shade=True,alpha=0.15, edgecolor="k")

        ax.scatter(best_posi[1] - self.HALF_WINDOW_SIZE + 0.5,
                    best_posi[0] - self.HALF_WINDOW_SIZE + 0.5, zs=0, marker="*", color='b', s=50)


        if iou_min is None:
            iou_min = IOU
        if iou_average is None:
            iou_average = IOU
        ax.title.set_text('step=%d,used_paint=%d,IOU=%.3f' % (step, brick, IOU))
        ax2.text(0, 20, 'Iou_min_iter_%d = %.3f' % (iter_times, iou_min), color='r', fontsize=12)
        ax2.text(0, 21.2, 'Iou_average_iter_%d = %.3f' % (iter_times, iou_average), color='b', fontsize=12)

        ax2.axis('off')
        plt.imshow(img)
        ax2.plot(best_posi[1] - self.HALF_WINDOW_SIZE,
                  best_posi[0] - self.HALF_WINDOW_SIZE, '*', color='b')
        save_plot(args, datetime)
        plt.draw()

    def _iou(self):
        plan = self.plan[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
               self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        env_memory = self.environment_memory[self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_height,
                     self.HALF_WINDOW_SIZE:self.HALF_WINDOW_SIZE + self.plan_width]

        env_memory_3d = np.zeros((self.plan_height, self.plan_width))
        for i in range(self.plan_height):
            for j in range(self.plan_width):
                if env_memory[i][j] > plan[i][j]:
                    env_memory_3d[i][j] = plan[i][j]
                else:
                    env_memory_3d[i][j] = env_memory[i][j]
        plan_area = self.total_brick
        env_area = self.count_brick
        cross_area = sum(map(sum, env_memory_3d))
        iou = cross_area / (plan_area + env_area - cross_area)
        return iou