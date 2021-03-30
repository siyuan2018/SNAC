# -*- coding: utf-8 -*-
"""
Created on Tue Jan 26 09:43:09 2021

@author: lelea
"""
import gym
import torch
from gym import spaces
from collections import defaultdict
import heapq
import matplotlib.pyplot as plt
import numpy as np
import sys
sys.path.append('../Env/1D/')
from DMP_Env_1D_static import deep_mobile_printing_1d1r

class RobotMove:
    def __init__(self, env):
        
        self.turn_left = 0
        self.turn_right = 1
        self.place_brick = 2
        self.env = env
        self.border = np.array([-1,-1])
        self.action = self.turn_right
        self.reward = 0
        self.observation = None
        self.done = False
        self.current_pos = self.env.HALF_WINDOW_SIZE
        self.saved_heights = np.zeros(len(self.env.plan) + 2 * self.env.HALF_WINDOW_SIZE)
        self.saved_heights[: self.env.HALF_WINDOW_SIZE] = -1
        self.saved_heights[-self.env.HALF_WINDOW_SIZE : ] = -1
        self.priority = self.turn_right
        


    def localize(self):

        step_sign = -1 if self.action == self.turn_left else 1

        start_step3 = (self.current_pos + 3 * step_sign)
        start_step3 = self.env.clip_position(start_step3) - self.env.HALF_WINDOW_SIZE
        end_step3 = start_step3 + 5
        start_step2 = (self.current_pos + 2 * step_sign ) 
        start_step2 = self.env.clip_position(start_step2) - self.env.HALF_WINDOW_SIZE
        end_step2 = start_step2 + 5
        start_step1 = (self.current_pos + 1 * step_sign ) 
        start_step1 = self.env.clip_position(start_step1) - self.env.HALF_WINDOW_SIZE
        end_step1 = start_step1 + 5

        is_3_steps = np.array_equal(self.observation[0, 0:5], self.saved_heights[start_step3 : end_step3 ])
        is_2_steps = np.array_equal(self.observation[0, 0:5], self.saved_heights[start_step2 : end_step2])
        is_1_step = np.array_equal(self.observation[0, 0:5], self.saved_heights[ start_step1 : end_step1])
        
        overlap = is_3_steps + is_2_steps + is_1_step
        left_most = self.env.HALF_WINDOW_SIZE
        right_most = len(self.saved_heights) - self.env.HALF_WINDOW_SIZE

        if self.current_pos + 2 * step_sign in (left_most, right_most) and not is_1_step and is_2_steps:
            self.current_pos += 2 * step_sign
            return
        elif overlap > 1: #odometry or current_pos at plan_width-1 where robot can only move 1 step to the right, vice versa for left
            self.current_pos += 1 * step_sign
            self.current_pos = self.env.clip_position(self.current_pos)
            print("overlapped ", self.current_pos)
            return

        if is_3_steps:
            self.current_pos += 3 * step_sign
        elif is_2_steps:
            self.current_pos += 2 * step_sign 
        elif is_1_step:
            self.current_pos += 1 * step_sign 

        self.current_pos = self.env.clip_position(self.current_pos)

    def plan(self):
        if self.done:
            return
        
        if self.saved_heights[self.current_pos] < self.env.plan[self.current_pos - self.env.HALF_WINDOW_SIZE]:
            self.observation, self.reward, self.done = self.env.step(self.place_brick)
            if isinstance(self.observation, list):
                self.observation = self.observation[0]
            self.saved_heights[self.current_pos] += 1
        else:
            pos = 2
            self.action = None 

            if np.array_equal(self.observation[0, 3:5], self.border):
                self.priority = self.turn_left
            elif np.array_equal(self.observation[0, :2], self.border):
                self.priority = self.turn_right

            for i in range(1, 3):
                if self.observation[0, pos + i] == 0 and self.observation[0, pos - i] == 0:
                    self.action = self.priority
                    break
                elif self.observation[0, pos + i] == 0:
                    self.action = self.turn_right
                    break
                elif self.observation[0, pos - i] == 0:
                    self.action = self.turn_left
                    break

            if self.action == None:
                self.action = self.priority

            

            self.observation, self.reward, self.done = self.env.step(self.action)
            if isinstance(self.observation, list):
                self.observation = self.observation[0]
            self.localize()
        
            
    def step(self):
        self.plan()
        return self.done
        
        


if __name__ == "__main__":

    env = deep_mobile_printing_1d1r(plan_choose=1)
    observation = env.reset()
    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(1, 1, 1)
    print(env.total_brick)
    print(env.one_hot)
    step = env.total_step
    ax.clear()
   

    
    robot_decider = RobotMove(env)
    done = False
    for i in range(step):

        done =  robot_decider.step()

        env.render(ax)
        env.iou()
        plt.pause(0.01)

        if done:
            break

    plt.show()