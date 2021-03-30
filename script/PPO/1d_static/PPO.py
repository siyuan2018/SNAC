from stable_baselines.common.policies import MlpPolicy, MlpLstmPolicy, MlpLnLstmPolicy
from stable_baselines.common import make_vec_env
from stable_baselines import PPO2

import time
from DMP_Env_1D_static import deep_mobile_printing_1d1r

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import tensorflow as tf

# env = make_vec_env('CartPole-v1', n_envs=4)

# model = PPO2(MlpPolicy, env, gamma=0.99, n_steps=128, noptepochs=4, ent_coef=0.01, learning_rate=0.00025, vf_coef=0.5, cliprange=0.2, nminibatches=4, verbose=1, tensorboard_log="./log_ppo/")

#Best model !!! Print_env_tuned_3 and 4
# model = PPO2(MlpPolicy, env, gamma=0.99, n_steps=400, noptepochs=4, ent_coef=0.01, learning_rate=0.00025, vf_coef=0.5, cliprange=0.2, nminibatches=4, verbose=1, tensorboard_log="./log_ppo/")

#Best model !!! Print_env_tuned_5
# model = PPO2(MlpPolicy, env, gamma=0.99, n_steps=400, noptepochs=4, ent_coef=0.01, learning_rate=0.00025, vf_coef=0.5, cliprange=0.1, nminibatches=4, verbose=1, tensorboard_log="./log_ppo/")


#     model = PPO2(MlpPolicy, env, gamma=0.99, n_steps=8000, noptepochs=4, ent_coef=0.01, learning_rate=0.00025, vf_coef=0.5, cliprange=0.1, nminibatches=80, verbose=1, tensorboard_log="./log_ppo/")



plan = 0
def main_exp(arg):
    env = deep_mobile_printing_1d1r(plan_choose=plan)
    env = make_vec_env(lambda: env, n_envs=1)
    policy_kwargs = dict(act_fun=tf.nn.tanh, net_arch=[512, 512, 512])
    model = PPO2(MlpPolicy, env, policy_kwargs=policy_kwargs, gamma=arg["gamma"], n_steps=arg["n_steps"], noptepochs=arg["noptepochs"], ent_coef=arg["ent_coef"], learning_rate=arg["learning_rate"], vf_coef=arg["vf_coef"], cliprange=arg["cliprange"], nminibatches=arg["nminibatches"], verbose=1, tensorboard_log="./log_ppo/")
    time_steps = 1e7
    model.learn(total_timesteps=int(time_steps), tb_log_name=arg["tb_log_name"])
    return model



if __name__ == "__main__":
    arg = {"gamma":0.99, "n_steps":100000, "noptepochs":4, "ent_coef":0.01, "learning_rate":0.00025, "vf_coef":0.5, "cliprange":0.1, "nminibatches":100, "tb_log_name":"best_args_3-512-tanh_uncertainty"}
    model = main_exp(arg)

    print(f"Testing plan {plan}")

    test_agent = model
    env = deep_mobile_printing_1d1r(plan_choose=plan)
    N_iteration_test = 500
    best_iou = 0
    iou_test_total = 0
    iou_min = 1
    reward_test_total = 0
    start_time_test = time.time()

    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(1, 1, 1)
    for ep in range(N_iteration_test):
        env = deep_mobile_printing_1d1r(plan_choose=plan)
        obs = env.reset()
        reward_test = 0

        while True:
            action, _ = test_agent.predict(obs)
            obs, r, done, info = env.step(action)
            reward_test += r
            if done:
                break

        iou_test = env.iou()
        iou_min = min(iou_min, iou_test)

        if iou_test > best_iou:
            best_iou = iou_test
            best_plan = env.plan
            best_tb = env.total_brick
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
    env.render(ax,iou_average=iou_test_total,iou_min=iou_min,iter_times=N_iteration_test)

    save_path = "plots/"
    plt.savefig(save_path+"PPO_Plan"+str(plan)+'.png')
