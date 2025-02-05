import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import sys
sys.path.append('../../Env/3D/')

from DMP_simulator_3d_dynamic_triangle import deep_mobile_printing_3d1r
import pickle

import math
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time
import os

from collections import deque
import random

log_path="./final_test/"

env = deep_mobile_printing_3d1r(plan_choose=0)

if os.path.exists(log_path)==False:
    os.makedirs(log_path)

## hyper parameter
minibatch_size=2000
Lr=0.001
N_iteration=3000
N_iteration_test=10
alpha=0.9
Replay_memory_size=50000
Update_traget_period=200
UPDATE_FREQ=1

Action_dim=env.action_dim
State_dim=env.state_dim
plan_dim=env.plan_width
INITIAL_EPSILON = 0.1
FINAL_EPSILON = 0.0



print("state_dim",State_dim)
print("total_step",env.total_step)
print("Action_dim",Action_dim)







def get_and_init_FC_layer(din, dout):
    li = nn.Linear(din, dout)
    li.weight.data.normal_(0, 0.1)
    return li



class Q_NET(nn.Module):
    def __init__(self, ):
        super(Q_NET, self).__init__()

        self.conv_layer1 = nn.Conv2d(in_channels=1,out_channels=16,kernel_size=3,stride=2) # potential check - in_channels
        self.conv_layer2 = nn.Conv2d(in_channels=16,out_channels=16,kernel_size=3,stride=2)
        self.conv_layer3 = nn.Conv2d(in_channels=16,out_channels=32,kernel_size=3,stride=2)
        self.conv_layer4 = nn.Conv2d(in_channels=32,out_channels=32,kernel_size=3,stride=2)


        self.fc_1 = get_and_init_FC_layer(State_dim+1+32, 64)
        self.fc_2 = get_and_init_FC_layer(64, 128)
        self.fc_3 = get_and_init_FC_layer(128, 128)
        self.out = get_and_init_FC_layer(128, 1)
        self.relu = nn.ReLU()
    def forward(self, s,a,plan,bsize):
        plan = plan.view(bsize,1,20,20) 
        conv_out = self.conv_layer1(plan)
        conv_out = self.relu(conv_out)
        conv_out = self.conv_layer2(conv_out)
        conv_out = self.relu(conv_out)
        
        conv_out = self.conv_layer3(conv_out)
        conv_out = self.relu(conv_out)
        conv_out = conv_out.view(bsize,32)


        x=torch.cat((s,a,conv_out),dim=1)
        x = self.fc_1(x)
        x = self.relu(x)
        x = self.fc_2(x)
        x = self.relu(x)
        x = self.fc_3(x)
        x = self.relu(x)
        Q = self.out(x)
        return Q


class DQN_AGNET():
    def __init__(self,device):
        self.Eval_net= Q_NET().to(device)
        self.Target_net = Q_NET().to(device)
        self.learn_step = 0                                     # counting the number of learning for update traget periodiclly 
        self.count_memory = 0                                         # counting the transitions 
        self.replay_memory = deque(maxlen=Replay_memory_size)    
        self.optimizer = torch.optim.Adam(self.Eval_net.parameters(), lr=Lr)
        self.greedy_epsilon=0.2
        self.loss = nn.SmoothL1Loss()
        self.loss_his=[]
    def store_memory(self,s,a,r,s_next,env_plan):
        self.replay_memory.append((s,a,r,s_next,env_plan))
        self.count_memory+=1
    def choose_action(self,s,env_plan):
        
        state=torch.FloatTensor(s).to(device)
        env_plan=torch.from_numpy(env_plan).float().to(device)
        env_plan=env_plan.unsqueeze(0)
        
        choose=np.random.uniform()
        Q=[]
        if choose<=self.greedy_epsilon:
            action=np.random.randint(0, Action_dim)         
        else:
            for item in range(Action_dim):
                a=torch.FloatTensor(np.array([item])).unsqueeze(0).to(device)

                Q_value=self.Eval_net(state,a,env_plan,1)
                Q.append(Q_value.item())  
            action=np.argmax(Q)    
        return action
    def learning_process(self):
        self.optimizer.zero_grad()
        self.Eval_net.train()
        if self.learn_step% Update_traget_period == 0:
            self.Target_net.load_state_dict(self.Eval_net.state_dict())
            
        minibatch = random.sample(self.replay_memory,minibatch_size)


        current_states = []
        acts = []
        rewards = []
        next_states = []
        env_plans = []
       
        for b in minibatch:
            current_states.append(b[0])
            acts.append(b[1])
            rewards.append(b[2])
            next_states.append(b[3])
            env_plans.append(b[4])
            
        current_states = np.array(current_states)
        # print("current_states_shape",current_states.shape)
        acts = np.array(acts).reshape(minibatch_size,1)
        # print("action_shape",acts.shape)
        rewards = np.array(rewards).reshape(minibatch_size,1)
        next_states = np.array(next_states)
        env_plans = np.array(env_plans)
        
        b_state = torch.from_numpy(current_states).float().to(device).squeeze(1)
        b_action = torch.from_numpy(acts).float().to(device)
        b_reward = torch.from_numpy(rewards).float().to(device)
        b_state_next = torch.from_numpy(next_states).float().to(device).squeeze(1)
        b_env_plans = torch.from_numpy(env_plans).float().to(device)

        Q_eval = self.Eval_net(b_state,b_action,b_env_plans,minibatch_size)
        Q=torch.zeros(minibatch_size,Action_dim).to(device)
        for item in range(Action_dim):
            a=torch.FloatTensor(np.array([item])).unsqueeze(0).to(device)
            a=a.expand(minibatch_size,-1)
            Q_value=self.Target_net(b_state_next,a,b_env_plans,minibatch_size).detach().squeeze(1)
            Q[:,item]=Q_value 
        Q_next=torch.max(Q,dim=1)[0].reshape(minibatch_size,1)
        Q_target = b_reward + alpha * Q_next
        loss = self.loss(Q_eval, Q_target)
        
        loss.backward()
        self.optimizer.step()
        self.learn_step+=1
        self.loss_his.append(loss.item())





device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
# device = torch.device("cpu")
agent=DQN_AGNET(device)


number_steps=0
while True:
    state = env.reset()
    prev_state=state[0]
    env_plan=state[1]
    while True:
        action = np.random.randint(0,Action_dim)
        next_state,reward,done = env.step(action)
        agent.store_memory(prev_state, action, reward, next_state[0],env_plan)
        prev_state = next_state[0]
        number_steps+=1

        if done:
            break
        if number_steps==Replay_memory_size:
            break
    if number_steps==Replay_memory_size:
            break


agent.greedy_epsilon=INITIAL_EPSILON

best_reward=0

total_steps = 0
reward_history_train=[]
reward_history_test=[]
iou_history_train=[]
iou_history_test=[]

for episode in range(N_iteration):
    state = env.reset()
    prev_state=state[0]
    env_plan=state[1]
    print("total_brick",env.total_brick)
    reward_train = 0
    start_time = time.time()
    while True:
        total_steps +=1
        action = agent.choose_action(prev_state,env_plan)

        state_next, r, done = env.step(action)

       
        agent.store_memory(prev_state, action, r, state_next[0],env_plan)
        reward_train += r
        if total_steps % UPDATE_FREQ == 0:
            agent.learning_process()
        if done:
            secs = int(time.time() - start_time)
            mins = secs / 60
            secs = secs % 60
            print(" | time in %d minutes, %d seconds\n" %(mins, secs))
            print('Epodise: ', episode,
                  '| Ep_reward: ', reward_train)
            reward_history_train.append(reward_train)
        if done:

            break
        prev_state = state_next[0]
    train_iou=env.iou()
    iou_history_train.append(train_iou)

    iou_test=0
    reward_test_total=0
    start_time_test = time.time()
    for _ in range(N_iteration_test):
        state = env.reset()
        prev_state=state[0]
        env_plan=state[1]
        reward_test=0
        while True:
      
            action = agent.choose_action(prev_state,env_plan)
            

            state_next, r, done = env.step(action)
            reward_test += r
            
            if done:

                break
            prev_state = state_next[0]
        reward_test_total+=reward_test
        iou_test+=env.iou()
    reward_test_total=reward_test_total/N_iteration_test
    secs = int(time.time() - start_time_test)
    mins = secs / 60
    secs = secs % 60
    print(" | time in %d minutes, %d seconds\n" %(mins, secs))
    print('Epodise: ', episode,
          '| Ep_reward_test:', reward_test_total)
    print('\nEpodise: ', episode,
          '| Ep_IOU_test: ', iou_test/N_iteration_test)

    reward_history_test.append(reward_test_total)
    iou_history_test.append(iou_test/N_iteration_test)


    if agent.greedy_epsilon > FINAL_EPSILON:
        agent.greedy_epsilon -= (INITIAL_EPSILON - FINAL_EPSILON)/N_iteration
        print("agent greedy_epsilon", agent.greedy_epsilon)
    




    if reward_test_total >= best_reward:
        torch.save(agent.Eval_net.state_dict(), log_path+'Eval_net_episode_%d.pth' % (episode))
        torch.save(agent.Target_net.state_dict(), log_path+'Target_net_episode_%d.pth' % (episode))

        with open(log_path+"brick.pickle", "wb") as fp: 
            pickle.dump(env.brick_memory, fp)
        with open(log_path+"position.pickle", "wb") as fp: 
            pickle.dump(env.position_memory, fp)
        best_reward=reward_test_total



with open(log_path+"brick_last.pickle", "wb") as fp: 
    pickle.dump(env.brick_memory, fp)
with open(log_path+"position_last.pickle", "wb") as fp: 
    pickle.dump(env.position_memory, fp)
        


with open(log_path+"reward_his_train.pickle", "wb") as fp: 
    pickle.dump(reward_history_train, fp)
with open(log_path+"reward_his_test.pickle", "wb") as fp: 
    pickle.dump(reward_history_test, fp)
with open(log_path+"loss.pickle", "wb") as fp: 
    pickle.dump(agent.loss_his, fp)  

with open(log_path+"iou_train_history.pickle", "wb") as fp: 
    pickle.dump(iou_history_train, fp) 
with open(log_path+"iou_test_history.pickle", "wb") as fp: 
    pickle.dump(iou_history_test, fp)  

    

    









