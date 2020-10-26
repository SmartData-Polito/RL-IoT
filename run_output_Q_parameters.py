import json
import os
import struct

import numpy as np
import csv
from threading import Thread
from time import sleep
import socket
import fcntl
from config import GlobalVar

# First, I should call put the transition to states and computation of reward inside external methods
# to call them from here, not to re-write them!

# Q will be read from output_Q_data.csv
# Retrieve actions and state from output_Q_data.csv
# Statistics to compute Q will be read from output_parameters_data.csv

# Identify which RL algorithm was used and use it
from utility_yeelight import bulbs_detection_loop, display_bulbs, operate_on_bulb, operate_on_bulb_json, \
    compute_reward_from_states, compute_next_state_from_props
from serve_yeelight import ServeYeelight


class RunOutputQParameters(object):
    def __init__(self, date='YY_mm_dd_HH_MM_SS'):
        if date != 'YY_mm_dd_HH_MM_SS':
            self.date = date  # Date must be in format %Y_%m_%d_%H_%M_%S
        else:
            print("Invalid date")
            exit(1)

    def run(self):
        directory = 'output_Q_parameters'
        file_Q = 'output_Q_' + self.date + '.csv'
        file_parameters = 'output_parameters_' + self.date + '.csv'

        actions = []
        states = []
        Q = []

        parameters = {}

        # Retrieving Q matrix, states and actions
        with open(directory + '/' + file_Q, 'r') as csv_file:
            reader = csv.reader(csv_file, delimiter=',')
            for index_row, row in enumerate(reader):
                if index_row == 0:  # Remember to remove first cell
                    for index_col, col in enumerate(row):
                        if index_col != 0:
                            actions.append(str(col.strip()))
                else:
                    for index_col, col in enumerate(row):
                        if index_col == 0:
                            states.append(str(col))

        try:
            tmp_matrix = np.genfromtxt(directory + '/' + file_Q, delimiter=',', dtype=np.float32)
            Q = tmp_matrix[1:, 1:]

        except Exception as e:
            print("Wrong file format:", e)
            exit(1)

        print(states)
        print(actions)
        print("Q matrix")
        print(Q)

        # TODO:
        # del tipo, runnare lo script con certi valori e verificare che il risultato sia quello scritto nei test
        # ad esempio certi valori di parametri, questa esatta lunghezza e questi esatti stati e azioni
        # il risultato deve essere coerente con ciò che mi aspetto
        # cosicche' cambiando parametri posso aspettarmi un risultato giusto

        if len(states) != len(Q) or len(actions) != len(Q[0]) or np.isnan(np.sum(Q)):
            print("Wrong file format: wrong Q dimensions or nan values present")
            exit(2)

        with open(directory + '/' + file_parameters, 'r') as csv_file:
            reader = csv.reader(csv_file, delimiter=',')
            parameters = {rows[0].strip(): rows[1].strip() for rows in reader}

        print(parameters)  # For now the are all strings
        # I think the optimal policy that I chose should be inserted into parameters,
        # otherwise I do not know how to compare results
        # I should check values using tests not prints!!!

        if parameters['num_actions_to_use'] is not None and len(actions) != int(parameters['num_actions_to_use']):
            print("Different number of actions used")
            exit(3)

        print("RL algorithm used:", parameters['algorithm_used'])

        if parameters['algorithm_used'] == 'sarsa_lambda':

            file_E = 'output_E_' + self.date + '.csv'

            E = []

            try:
                tmp_matrix = np.genfromtxt(directory + '/' + file_E, delimiter=',', dtype=np.float32)
                E = tmp_matrix[1:, 1:]

                if len(states) != len(E) or len(actions) != len(E[0]) or np.isnan(np.sum(E)):
                    print("Wrong file format: wrong E dimensions or nan values present")
                    exit(4)

            except Exception as e:
                print("Wrong file format:", e)
                exit(5)

            print("E matrix")
            print(E)

        optimal_policy = parameters['optimal_policy'].split('-')  # Split policy string and save it into a list

        print("Optimal policy:", optimal_policy)
        # I should check values using tests not prints!!!

        #### FOLLOW POLICY ####
        seconds_to_wait = int(parameters['seconds_to_wait'])
        # Then I can follow the found optimal policy:
        print("------------------------------------------")
        print("Follow policy")
        print("\t\tREQUEST: Setting power off")
        operate_on_bulb(idLamp, "set_power", str("\"off\", \"sudden\", 0"))
        sleep(seconds_to_wait)
        state1, old_props_values = compute_next_state_from_props(idLamp, 0, [])
        print("\tSTARTING FROM STATE", states[state1])

        t = 0
        final_policy = []
        final_reward = 0

        while t < 20:
            max_action = np.argmax(Q[state1, :])
            final_policy.append(max_action)
            print("\tACTION TO PERFORM", max_action)

            json_string = ServeYeelight(id_lamp=idLamp, method_chosen_index=max_action).run()
            print("\t\tREQUEST:", str(json_string))
            reward_from_response = operate_on_bulb_json(idLamp, json_string)
            sleep(seconds_to_wait)

            state2, new_props_values = compute_next_state_from_props(idLamp, state1, old_props_values)

            print("\tFROM STATE", states[state1], "TO STATE", states[state2])

            reward_from_props = compute_reward_from_states(state1, state2)

            tmp_reward = -1 + reward_from_response + reward_from_props  # -1 for using a command more
            print("\tTMP REWARD:", str(tmp_reward))
            final_reward += tmp_reward

            if state2 == 5:
                print("Done")
                break
            state1 = state2
            old_props_values = new_props_values
            t += 1

        print("\tRESULTS:")
        print("\t\tLength final policy:", len(final_policy))
        print("\t\tFinal policy:", final_policy)
        if len(final_policy) == len(optimal_policy) and np.array_equal(final_policy, optimal_policy):
            print("\t\tOptimal policy found with reward: " + str(final_reward))
        else:
            print("\t\tNot optimal policy found with reward: " + str(final_reward))

        # First, connecting to the device, initialization, something like this:


if __name__ == '__main__':
    # Socket setup
    GlobalVar.scan_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fcntl.fcntl(GlobalVar.scan_socket, fcntl.F_SETFL, os.O_NONBLOCK)
    GlobalVar.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    GlobalVar.listen_socket.bind(("", 1982))
    fcntl.fcntl(GlobalVar.listen_socket, fcntl.F_SETFL, os.O_NONBLOCK)
    # GlobalVar.scan_socket.settimeout(GlobalVar.timeout)  # set 2 seconds of timeout
    # GlobalVar.listen_socket.settimeout(GlobalVar.timeout)
    mreq = struct.pack("4sl", socket.inet_aton(GlobalVar.MCAST_GRP), socket.INADDR_ANY)
    GlobalVar.listen_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # first discover the lamp and Connect to the lamp
    # start the bulb detection thread
    detection_thread = Thread(target=bulbs_detection_loop)
    detection_thread.start()
    # give detection thread some time to collect bulb info
    sleep(10)

    # show discovered lamps
    display_bulbs()

    print(GlobalVar.bulb_idx2ip)
    max_wait = 0
    while len(GlobalVar.bulb_idx2ip) == 0 and max_wait < 10:
        sleep(1)
        max_wait += 1
    if len(GlobalVar.bulb_idx2ip) == 0:
        print("Bulb list is empty.")
    else:
        display_bulbs()
        idLamp = list(GlobalVar.bulb_idx2ip.keys())[0]

        print("Waiting 5 seconds before verifying optimal policy")
        sleep(5)

        GlobalVar.RUNNING = False

        RunOutputQParameters(date="2020_10_25_22_28_49").run()

    # goal achieved, tell detection thread to quit and wait
    RUNNING = False
    detection_thread.join()
    # done
