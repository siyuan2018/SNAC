import numpy as np
import math
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import gym
from gym import spaces


class MDP_deep_mobile_printing_1d1r(gym.Env):
    def __init__(self, plan_choose=0):

        self.step_size = 1
        self.plan_width = 30  # plan parameters: width, height, base_line
        self.plan_height = 20
        self.environment_height = 100
        self.environment_memory = None
        self.conut_brick = None
        self.brick_memory = None
 

        self.wall = np.ones((1, 2)) * (-1)
        self.position_memory = None
        self.observation = None
        self.count_step = 0
        self.total_step = 750
        self.plan = None
        self.total_brick = 0
        self.one_hot = None

        # Need to define gym spaces to use stable_baseline code
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(low=np.zeros(self.plan_width), high=100*np.ones(self.plan_width), dtype=np.int)

        self.action_dim = 3
        self.plan_choose = plan_choose

    def normal_distribution(self, x, mean, sigma):
        return np.exp(-1 * ((x - mean) ** 2) / (2 * (sigma ** 2))) / (math.sqrt(2 * np.pi) * sigma)

    def create_plan(self):
        # 0 Sin, 1 Gaussian, 2 Step
        self.one_hot = self.plan_choose
        if self.plan_choose == 0:
            x = np.arange(self.plan_width)
            y = np.round(10 * np.sin(2 * np.pi / self.plan_width * x) + self.plan_height)

        elif self.plan_choose == 1:
            mean1, sigma1 = 0, 3

            x = np.linspace(mean1 - 6 * sigma1, mean1 + 6 * sigma1, 30)
            y = np.round(self.normal_distribution(x, mean1, sigma1) * 100 + 17)
        elif self.plan_choose ==2:
            y = np.ones(30, ) * 15
            y[0:5] = 25
            y[10:15] = 25
            y[20:25] = 25
        else:
            raise ValueError('0: Sin, 1: Gaussian, 2: Step')
        area = sum(y)

        return y, area

    def clip_position(self, position):
        if position < 0:
            position = 0
        elif position > self.plan_width - 1:
            position = self.plan_width - 1
        else:
            position = position
        return position

    def reset(self):
        self.one_hot = None
        self.plan, self.total_brick = self.create_plan()
        self.environment_memory = np.zeros(self.plan_width)

        self.conut_brick = 0
        self.brick_memory = []
        self.position_memory = []
        self.observation = None
        self.count_step = 0

        initial_position = 2

        self.position_memory.append(initial_position)
        self.brick_memory.append([-1, -1])
        return self.environment_memory

    def step(self, action):
        info = {}
        self.count_step += 1
        self.step_size = np.random.randint(1, 4)

        if action == 0:
            position = self.position_memory[-1] - self.step_size
            position = self.clip_position(position)
            self.position_memory.append(position)
            self.brick_memory.append([-1, -1])

        if action == 1:
            position = self.position_memory[-1] + self.step_size
            position = self.clip_position(position)
            self.position_memory.append(position)
            self.brick_memory.append([-1, -1])
        if action == 2:
            self.conut_brick += 1
            position = self.position_memory[-1]
            self.position_memory.append(position)
            self.environment_memory[position] += 1
            self.brick_memory.append([position, self.environment_memory[position]])

            done = bool(self.conut_brick >= self.total_brick)
            if done:
                reward = 0.0
                return self.environment_memory, reward, done, info
            else:
                done = bool(self.count_step >= self.total_step)
                if self.environment_memory[position] > self.plan[position]:

                    reward = -1.0
                elif self.environment_memory[position] == self.plan[position]:
                    reward = 10.0
                else:
                    reward = 1.0
                return self.environment_memory, reward, done, info
        done = bool(self.count_step >= self.total_step)
        reward = 0
        return self.environment_memory, reward, done, info

    def iou(self):
        component1 = self.plan
        component2 = self.environment_memory

        area1 = sum(component1)
        area2 = sum(component2)
        k = 0
        for i in range(self.plan_width):
            if component2[i] > component1[i]:
                j = component2[i] - component1[i]
                k += j
        area_cross = area2 - k
        iou = area_cross / (area1 + area2 - area_cross)
        return iou

    def render(self, axe, iou_min=None, iou_average=None, iter_times=100):
        axe.clear()
        axe.set_xlabel('X-axis')
        axe.set_xlim(-1, 30)
        axe.set_ylabel('Y-axis')
        axe.set_ylim(0, 50)
        x = np.arange(self.plan_width)
        IOU = self.iou()
        plan = self.plan
        env_memory = self.environment_memory
        axe.title.set_text('step=%d,used_paint=%d,IOU=%.3f' % (self.count_step, self.conut_brick, IOU))
        axe.plot(x, plan, color='b')

        axe.bar(x, env_memory - 1, color='r')

        if iou_min == None:
            iou_min = IOU
        if iou_average == None:
            iou_average = IOU
        plt.text(12, 46, 'Iou_min_iter_%d = %.3f' % (iter_times, iou_min), color='red', fontsize=10)
        plt.text(12, 48, 'Iou_average_iter_%d = %.3f' % (iter_times, iou_average), color='blue', fontsize=10)

        plt.draw()


if __name__ == "__main__":

    env = MDP_deep_mobile_printing_1d1r(plan_choose=1)
    observation = env.reset()
    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(1, 1, 1)
    print(env.total_brick)
    print(env.one_hot)
    step = env.total_step
    ax.clear()
    for i in range(step):
        action = np.random.randint(0, 3, (1,))
        observation, reward, done = env.step(action)
        env.render(ax)
        env.iou()
        plt.pause(0.01)
    plt.show()
