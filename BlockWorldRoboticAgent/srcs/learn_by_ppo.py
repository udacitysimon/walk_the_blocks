#!/usr/bin/python 

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
import torch.nn.init as init
from agent import *
from policy_model import *
from copy import deepcopy
import constants
from config import Config
import collections
import numpy as np
import pickle

from tensorboard_logger import configure, log_value

def ppo_step(agent, opti, args):
	img_state = collections.deque([], 5)
	init_imgs = agent.policy_model.image_encoder.build_init_images()
	for img in init_imgs:
		img_state.append(img)
	(_, bisk_metric, img, instruction, traj) = agent.receive_instruction_image()
	img = np.transpose(img, (2,0,1))
	img_state.append(img)
	previous_direction = agent.null_previous_direction
	previous_block = agent.null_previous_block
	instruction_ids = agent.policy_model.seq_encoder.instruction2id(instruction)
	state = (img_state, instruction_ids, previous_direction, previous_block)
	inputs = agent.build_batch_inputs([(state, 0, 0)])

	gold_block_id = traj[0] / 4
	replay_memory = []
	steps = 0
	rewards = []
	baselines = []

	# roll out
	while True:
		d_probs, b_probs, baseline = agent.policy_model(inputs)
		d_id = agent.sample_policy(d_probs, method='random')
		b_id = agent.sample_policy(b_probs, method='random')
		# b_id = agent.sample_policy(b_probs, method='greedy')
		baseline = baseline.squeeze()
		baselines.append(baseline.data.cpu().numpy()[0])
		# b_id = gold_block_id
		action_msg = agent.action2msg(b_id, d_id)
		agent.connection.send_message(action_msg)

		(_, reward, new_img, is_reset) = agent.receive_response()
		new_img = np.transpose(new_img, (2,0,1))
		rewards.append(reward)
		replay_memory_item = (deepcopy(state), b_id, d_id)
		replay_memory.append(replay_memory_item)

		if agent.message_protocol_kit.is_reset_message(is_reset):
			agent.connection.send_message('Ok-Reset')
			break	

		img_state.append(new_img)
		previous_direction = d_id
		previous_block = b_id
		state = (img_state, instruction_ids, previous_direction, previous_block)
		inputs = agent.build_batch_inputs([(state, 0, 0)])

	# rewards_final = [0] * len(rewards)
	# for _ in range(len(rewards)):
	# 	rewards_final[_] = sum(rewards[_:])
	batch = agent.build_batch_inputs(replay_memory)

	# a2c_loss, entropy = agent.policy_model.a2c_loss(batch, baselines, rewards, args)
	# opti.zero_grad()
	# a2c_loss.backward()
<<<<<<< HEAD
	# # nn.utils.clip_grad_norm(agent.policy_model.parameters(), 5.0)
	# opti.step()

	reinforce_loss, entropy = agent.policy_model.reinforce_loss(batch, rewards, args)
	opti.zero_grad()
	reinforce_loss.backward()
	# nn.utils.clip_grad_norm(agent.policy_model.parameters(), 10.0)
	opti.step()

	# old_model = deepcopy(agent.policy_model)
	# old_model.load_state_dict(agent.policy_model.state_dict())
	# for _ in range(args.ppo_epoch):
	# 	ppo_loss, entropy = agent.policy_model.ppo_loss(batch, old_model, rewards, baselines, args)
	# 	final_loss = ppo_loss
	# 	opti.zero_grad()
	# 	final_loss.backward()
	# 	# nn.utils.clip_grad_norm(agent.policy_model.parameters(), 5.0)
	# 	opti.step()
=======
	# opti.step()

	old_model = deepcopy(agent.policy_model)
	old_model.load_state_dict(agent.policy_model.state_dict())
	for _ in range(args.ppo_epoch):
		ppo_loss, entropy = agent.policy_model.ppo_loss(batch, old_model, rewards, baselines, args)
		final_loss = ppo_loss
		opti.zero_grad()
		final_loss.backward()
		# nn.utils.clip_grad_norm(agent.policy_model.parameters(), 5.0)
		opti.step()
>>>>>>> master

	return bisk_metric, entropy.data.cpu().numpy()

def sl_step(agent, sl_opti, args):
	img_state = collections.deque([], 5)
	init_imgs = agent.policy_model.image_encoder.build_init_images()
	for img in init_imgs:
		img_state.append(img)
	(_, _, img, instruction, traj) = agent.receive_instruction_image()
	img = np.transpose(img, (2,0,1))
	img_state.append(img)
	previous_direction = agent.null_previous_direction
	previous_block = agent.null_previous_block
	instruction_ids = agent.policy_model.seq_encoder.instruction2id(instruction)
	state = (img_state, instruction_ids, previous_direction, previous_block)

	path = []
	traj_index = 0
	while True:
		action_id = traj[traj_index]
		block_id = action_id / 4
		if action_id == 80:
			direction_id = 4
			block_id = traj[traj_index - 1] / 4
		else:
			direction_id = action_id % 4
		path.append((deepcopy(state), block_id, direction_id))
		action_msg = agent.action2msg(block_id, direction_id)
		agent.connection.send_message(action_msg)
		traj_index += 1
		(status_code, reward, new_img, is_reset) = agent.receive_response()
		new_img = np.transpose(new_img, (2,0,1))
		img_state.append(new_img)
		previous_direction = direction_id
		previous_block = block_id
		state = (img_state, instruction_ids, previous_direction, previous_block)

		if agent.message_protocol_kit.is_reset_message(is_reset):
			agent.connection.send_message('Ok-Reset')
			break

	expert_batch = agent.build_batch_inputs(path)
	sl_loss, _ = agent.policy_model.sl_loss(expert_batch, args.entropy_coef)
	sl_opti.zero_grad()
	sl_loss.backward()
	sl_opti.step()

	_, entropy = agent.policy_model.sl_loss(expert_batch, args.entropy_coef)
	return entropy.data.cpu().numpy()

def ppo_update(agent):
	parser = argparse.ArgumentParser(description='PPO update')
<<<<<<< HEAD
	parser.add_argument('-max_epochs', type=int, default=4, help='training epochs')
	parser.add_argument('-lr', type=float, default=0.000025, help='learning rate')
=======
	parser.add_argument('-max_epochs', type=int, default=2, help='training epochs')
	parser.add_argument('-lr', type=float, default=0.0001, help='learning rate')
>>>>>>> master
	parser.add_argument('-ppo_epoch', type=int, default=4)
	parser.add_argument('-clip_epsilon', type=float, default=0.05)
	parser.add_argument('-entropy_coef', type=float, default=0.1, help='weight for entropy loss')
	parser.add_argument('-id', default='ppo', help='model setting')
	parser.add_argument('-saved_model', default='')
	args = parser.parse_args()

	opti = torch.optim.Adam(agent.policy_model.parameters(), lr=args.lr)

	configure('runs/' + args.id, flush_secs=0.5)

	# load from saved model
	if args.saved_model != '':
		agent.policy_model.load_state_dict(torch.load('../models/' + args.saved_model))
		print 'Pretrained model reloaded'

	constants_hyperparam = constants.constants
	config = Config.parse("../../simulator2/Assets/config.txt")
	assert config.data_mode == Config.TRAIN
	dataset_size = constants_hyperparam["train_size"]

	bisk_metrics = collections.deque([], 100)
<<<<<<< HEAD
	# policy_entropy = collections.deque([], 200)
	plot_data = []
	plot_time = []
	sl = False
	step = 0
=======
	entropies = collections.deque([], 100)
	# plot_data = []
	# plot_time = []
	sl = False
	step = 0
	plot_entropy = []
	plot_entropy_time = []
>>>>>>> master

	for epoch in range(args.max_epochs):
		# f = open('../demonstrations.pkl', 'rb')
		# if epoch == 4:
		# 	opti = torch.optim.Adam(agent.policy_model.parameters(), lr=args.lr / 2)
		# 	bisk_metrics = collections.deque([], 100)

		for sample_id in tqdm(range(dataset_size)):
			step += 1
<<<<<<< HEAD

			# schedule rule
			if sl:
				entropy = sl_step(agent, opti, args)
				sl = False
			else:
				dis, _ = ppo_step(agent, opti, args)
				# if dis > 0.5:
				bisk_metrics.append(dis)
				if len(bisk_metrics) != 0 and dis > np.mean(bisk_metrics): # performance lower than baselines
					sl = True
				if len(bisk_metrics) > 0:
					log_value('avg_dis', np.mean(bisk_metrics), step)	
					plot_data.append(np.mean(bisk_metrics))
					plot_time.append(step)

			# # schedule every 100
			# if (sample_id + 1) % 100 == 0:
			# 	_ = sl_step(agent, opti, args)
			# else:
=======
			# schedule rule
			# if sl:
			entropy = sl_step(agent, opti, args)
			entropies.append(entropy)
			plot_entropy.append(np.mean(entropies))
			plot_entropy_time.append(step)
			log_value('entropy_plot', np.mean(entropies), step)
				# sl = False
			# else:
			# 	dis, entropy = ppo_step(agent, opti, args)
			# 	# if dis > 0.5:
			# 	bisk_metrics.append(dis)
			# 	entropies.append(entropy)
			# 	plot_entropy.append(np.mean(entropies))
			# 	plot_entropy_time.append(step)
			# 	log_value('entropy_plot', np.mean(entropies), step)
			# 	if len(bisk_metrics) != 0 and dis > np.mean(bisk_metrics): # performance lower than baselines
			# 		sl = True
				# if len(bisk_metrics) > 0:
				# 	log_value('avg_dis', np.mean(bisk_metrics), step)	
				# 	plot_data.append(np.mean(bisk_metrics))
				# 	plot_time.append(step)


			# # schedule every 100
			# if (sample_id + 1) % 100 == 0:
			# 	_ = sl_step(agent, opti, args)
			# else:
>>>>>>> master
			# 	dis, _ = ppo_step(agent, opti, args)
			# 	if dis > 0.5:
			# 		bisk_metrics.append(dis)
			# 	log_value('avg_dis', np.mean(bisk_metrics), step)	
			# 	plot_data.append(np.mean(bisk_metrics))
			# 	plot_time.append(step)

<<<<<<< HEAD
			# imitation 1 epoch, RL 1 epoch
			# if epoch < 2:
			# 	_ = sl_step(agent, opti, args)
			# else:
			# 	dis, _ = ppo_step(agent, opti, args)
			# 	# if dis > 0.5:
			# 	bisk_metrics.append(dis)
=======
			# # imitation 1 epoch, RL 1 epoch
			# if epoch == 0:
			# 	_ = sl_step(agent, opti, args)
			# else:
			# 	dis, _ = ppo_step(agent, opti, args)
			# 	if dis > 0.5:
			# 		bisk_metrics.append(dis)
>>>>>>> master
			# 	log_value('avg_dis', np.mean(bisk_metrics), step)
			# 	plot_data.append(np.mean(bisk_metrics))
			# 	plot_time.append(step)

<<<<<<< HEAD
			# Pure PPO
=======
			# # Pure PPO
>>>>>>> master
			# dis, _ = ppo_step(agent, opti, args)
			# bisk_metrics.append(dis)
			# log_value('avg_dis', np.mean(bisk_metrics), step)
			# plot_data.append(np.mean(bisk_metrics))
			# plot_time.append(step)

<<<<<<< HEAD
		save_path = '../models/' + args.id + '_epoch' + str(epoch + 9) + '.pth'
		torch.save(agent.policy_model.state_dict(), save_path)
		print 'Model Saved'
	
	# np.save('../plot_data/' + args.id, np.array(plot_data))
	# np.save('../plot_data/' + args.id + '_steps', np.array(plot_time))
	# print 'Plotdata Saved'

if __name__ == '__main__':
	torch.manual_seed(3)
	torch.cuda.manual_seed(3)
	agent = Agent()
=======
		# save_path = '../models/' + args.id + '_epoch' + str(epoch + 1) + '.pth'
		# torch.save(agent.policy_model.state_dict(), save_path)
		# print 'Model Saved'
	
	np.save('../plot_data/' + args.id, np.array(plot_entropy))
	np.save('../plot_data/' + args.id + '_steps', np.array(plot_entropy_time))
	print 'Plotdata Saved'

if __name__ == '__main__':
	torch.manual_seed(2)
	torch.cuda.manual_seed(2)
	agent = Inverse_agent()
>>>>>>> master
	agent.policy_model.cuda()
	ppo_update(agent)
