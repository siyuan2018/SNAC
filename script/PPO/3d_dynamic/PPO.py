from stable_baselines.common.policies import MlpPolicy, MlpLstmPolicy, MlpLnLstmPolicy
from stable_baselines.common import make_vec_env
from stable_baselines import PPO2

import time
import DMP_simulator_3d_dynamic_triangle_test
import DMP_simulator_3d_dynamic_triangle

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import tensorflow as tf

plan_choose = 0
def main_exp(arg):
    env = DMP_simulator_3d_dynamic_triangle.deep_mobile_printing_3d1r(plan_choose=plan_choose)
    env = make_vec_env(lambda: env, n_envs=1)
    policy_kwargs = dict(act_fun=tf.nn.tanh, net_arch=[512, 512, 512])
    model = PPO2(MlpPolicy, env, policy_kwargs=policy_kwargs, gamma=arg["gamma"], n_steps=arg["n_steps"], noptepochs=arg["noptepochs"], ent_coef=arg["ent_coef"], learning_rate=arg["learning_rate"], vf_coef=arg["vf_coef"], cliprange=arg["cliprange"], nminibatches=arg["nminibatches"], verbose=1, tensorboard_log="./log_ppo/")
    time_steps = 1e7
    model.learn(total_timesteps=int(time_steps), tb_log_name=arg["tb_log_name"])
    return model


arg = {"gamma":0.99, "n_steps":100000, "noptepochs":4, "ent_coef":0.01, "learning_rate":0.00025, "vf_coef":0.5, "cliprange":0.1, "nminibatches":100, "tb_log_name":"best_args_3-512-tanh_uncertainty"}
test_agent = main_exp(arg)
print("Testing")


print(f"PLAN = {plan_choose}")
iou_all_average = 0
iou_all_min = 1
for test_set in range(10):
    env = DMP_simulator_3d_dynamic_triangle_test.deep_mobile_printing_3d1r(plan_choose=plan_choose, test_set=test_set)


    def iou(environment_memory,environment_plan,HALF_WINDOW_SIZE,plan_height,plan_width):
        component1=environment_plan[HALF_WINDOW_SIZE:HALF_WINDOW_SIZE+plan_height,\
                           HALF_WINDOW_SIZE:HALF_WINDOW_SIZE+plan_width].astype(bool)
        component2=environment_memory[HALF_WINDOW_SIZE:HALF_WINDOW_SIZE+plan_height,\
                           HALF_WINDOW_SIZE:HALF_WINDOW_SIZE+plan_width].astype(bool)
        overlap = component1*component2 # Logical AND
        union = component1 + component2 # Logical OR
        IOU = overlap.sum()/float(union.sum())
        return IOU

    print(test_set)
    N_iteration_test = 200
    best_iou = 0
    iou_test_total = 0
    iou_min = 1
    reward_test_total = 0
    start_time_test = time.time()

    fig = plt.figure(figsize=[10, 5])
    ax1 = fig.add_subplot(1, 2, 1, projection='3d')
    ax2 = fig.add_subplot(1, 2, 2)

    for ep in range(N_iteration_test):
        obs = env.reset()
        reward_test = 0

        while True:
            action, _ = test_agent.predict(obs)
            obs, r, done, info = env.step(action)
            reward_test += r
            if done:
                break

        iou_test = iou(env.environment_memory,env.plan,env.HALF_WINDOW_SIZE,env.plan_height,env.plan_width)
        iou_min = min(iou_min, iou_test)

        if iou_test > best_iou:
           best_iou = iou_test
           best_plan = env.plan
           best_step = env.count_step
           best_brick = env.count_brick
           best_tb = env.total_brick
           best_env = env.environment_memory
        iou_test_total += iou_test
        reward_test_total += reward_test

    reward_test_total = reward_test_total / N_iteration_test
    iou_test_total = iou_test_total / N_iteration_test
    secs = int(time.time() - start_time_test)
    mins = secs // 60
    secs = secs % 60
    print(f"time = {mins} min {secs} sec")
    print(f"iou = {iou_test_total}")
    print(f"reward_test = {reward_test_total}")
    if best_iou>0:
        env.render(ax1,ax2,iou_average=iou_test_total,iou_min=iou_min,iter_times=N_iteration_test,best_env=best_env,best_iou=best_iou,best_step=best_step,best_brick=best_brick)
    else:
        env.render(ax1,ax2,iou_average=iou_test_total,iou_min=iou_min,iter_times=N_iteration_test)
    save_path = "plots/"
    plt.savefig(save_path + "PPO_Plan" + str(plan_choose) +'_test'+str(test_set) + '.png')

    iou_all_average += iou_test_total
    iou_all_min = min(iou_min,iou_all_min)

iou_all_average = iou_all_average/10
print('iou_all_average',iou_all_average)
print('iou_all_min',iou_all_min)
