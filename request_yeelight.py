#!/usr/bin/python

import random
import socket
import sys
import time
import fcntl
import re
import os
import errno
import struct
from threading import Thread
from time import sleep
from collections import OrderedDict

# Global variables
detected_bulbs = {}
bulb_idx2ip = {}
RUNNING = True
current_command_id = 0
MCAST_GRP = '239.255.255.250'

# Socket setup
scan_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
fcntl.fcntl(scan_socket, fcntl.F_SETFL, os.O_NONBLOCK)
listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
listen_socket.bind(("", 1982))
fcntl.fcntl(listen_socket, fcntl.F_SETFL, os.O_NONBLOCK)
mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
listen_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

sleep(2)


def next_cmd_id():
    global current_command_id
    current_command_id += 1
    return current_command_id


def send_search_broadcast():
  # multicast search request to all hosts in LAN, do not wait for response
    print("send_search_broadcast running")
    multicase_address = (MCAST_GRP, 1982)
    msg = "M-SEARCH * HTTP/1.1\r\n"
    msg = msg + "HOST: 239.255.255.250:1982\r\n"
    msg = msg + "MAN: \"ssdp:discover\"\r\n"
    msg = msg + "ST: wifi_bulb"
    scan_socket.sendto(msg.encode(), multicase_address)


def bulbs_detection_loop():
  # a standalone thread broadcasting search request and listening on all responses
    print("bulbs_detection_loop running")
    search_interval = 30000
    read_interval = 100
    time_elapsed = 0

    while RUNNING:
        if time_elapsed % search_interval == 0:
            send_search_broadcast()

        # scanner
        while True:
            try:
                data = scan_socket.recv(2048)
            except socket.error as e:
                err = e.args[0]
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                    break
                else:
                    print(e)
                    sys.exit(1)
            handle_search_response(data)

        # passive listener
        while True:
            try:
                data, addr = listen_socket.recvfrom(2048)
            except socket.error as e:
                err = e.args[0]
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                    break
                else:
                    print(e)
                    sys.exit(1)
            handle_search_response(data)

        time_elapsed += read_interval
        sleep(read_interval / 1000.0)
    scan_socket.close()
    listen_socket.close()


def get_param_value(data, param):
    '''
  match line of 'param = value'
  '''
    param_re = re.compile(param + ":\s*([ -~]*)")  # match all printable characters
    match = param_re.search(data.decode())
    value = ""
    if match != None:
        value = match.group(1)
        return value


def handle_search_response(data):
    '''
  Parse search response and extract all interested data.
  If new bulb is found, insert it into dictionary of managed bulbs.
  '''
    location_re = re.compile("Location.*yeelight[^0-9]*([0-9]{1,3}(\.[0-9]{1,3}){3}):([0-9]*)")
    match = location_re.search(data.decode())
    if match == None:
        print("invalid data received: " + data.decode())
        return

    host_ip = match.group(1)
    if host_ip in detected_bulbs:
        bulb_id = detected_bulbs[host_ip][0]
    else:
        bulb_id = len(detected_bulbs) + 1
    host_port = match.group(3)
    model = get_param_value(data, "model")
    power = get_param_value(data, "power")
    bright = get_param_value(data, "bright")
    rgb = get_param_value(data, "rgb")
    # use two dictionaries to store index->ip and ip->bulb map
    detected_bulbs[host_ip] = [bulb_id, model, power, bright, rgb, host_port]
    bulb_idx2ip[bulb_id] = host_ip


def handle_response(data):
    # Print response
    print(data.decode())


def display_bulb(idx):
    if idx not in bulb_idx2ip:
        print("error: invalid bulb idx")
        return
    bulb_ip = bulb_idx2ip[idx]
    model = detected_bulbs[bulb_ip][1]
    power = detected_bulbs[bulb_ip][2]
    bright = detected_bulbs[bulb_ip][3]
    rgb = detected_bulbs[bulb_ip][4]
    print(str(idx) + ": ip=" \
          + bulb_ip + ",model=" + model \
          + ",power=" + power + ",bright=" \
          + bright + ",rgb=" + rgb)


def display_bulbs():
    print(str(len(detected_bulbs)) + " managed bulbs")
    for i in range(1, len(detected_bulbs) + 1):
        display_bulb(i)


def operate_on_bulb(idx, method, params):
    '''
  Operate on bulb; no gurantee of success.
  Input data 'params' must be a compiled into one string.
  E.g. params="1"; params="\"smooth\"", params="1,\"smooth\",80"
  '''
    if idx not in bulb_idx2ip:
        print("error: invalid bulb idx")
        return

    bulb_ip = bulb_idx2ip[idx]
    port = detected_bulbs[bulb_ip][5]
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("connect ", bulb_ip, port, "...")
        tcp_socket.connect((bulb_ip, int(port)))
        msg = "{\"id\":" + str(next_cmd_id()) + ",\"method\":\""
        msg += method + "\",\"params\":[" + params + "]}\r\n"
        tcp_socket.send(msg.encode())
        tcp_socket.close()
    except Exception as e:
        print("Unexpected error:", e)


# MAIN

# first discover the lamp and Connect to the lamp
# start the bulb detection thread
detection_thread = Thread(target=bulbs_detection_loop)
detection_thread.start()
# give detection thread some time to collect bulb info
sleep(5)

# show discovered lamps
display_bulbs()

print(bulb_idx2ip)
idLamp = 1

# Setting power off if open
print("Setting power off")
operate_on_bulb(idLamp, "set_power", str("\"off\", \"smooth\", 500"))
sleep(2)

# Toggle
print("Toggling lamp")
operate_on_bulb(idLamp, "toggle", "")

sleep(2)

data = ""

while data == "":
    try:
        data, addr = listen_socket.recvfrom(2048)
    except socket.error as e:
        err = e.args[0]
        if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
            print("Socket error occurred")
            break
        else:
            print(e)
            sys.exit(1)
    handle_response(data)

# Set brightness
print("Changing brightness")
brightness = random.randint(1, 100)
operate_on_bulb(idLamp, "set_bright", str(1000))

sleep(2)

# Set rgb
print("Changing color rgb")
rgb = random.randint(1, 16777215)
operate_on_bulb(idLamp, "set_rgb", str(str(rgb) + ", \"smooth\", 500"))

sleep(2)

# Toggle
print("Toggling lamp")
operate_on_bulb(idLamp, "toggle", "")

# goal achieved, tell detection thread to quit and wait
RUNNING = False
detection_thread.join()
# done
