#!/usr/bin/env python -u

__author__ = 'timmattison'

import pyuda
import re
import paramiko
import sys
import time
import select
import termios
import tty
import socket

buffer_size = 8192

# For debugging only
# paramiko.common.logging.basicConfig(level=paramiko.common.DEBUG)

stdin_fd = sys.stdin.fileno()


def enter_raw_terminal_mode():
    # Assume we will need to restore the settings
    restore_settings = True

    try:
        old_settings = termios.tcgetattr(stdin_fd)
        tty.setraw(sys.stdin.fileno())

        return old_settings
    except termios.error:
        # Throws "termios.error: (25, 'Inappropriate ioctl for device')" if running in a debugger/PyCharm

        # No settings to restore
        return None


def exit_raw_terminal_mode(old_settings):
    if (old_settings == None):
        return

    termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)


def send_stdin_data():
    # https://stackoverflow.com/questions/510357/python-read-a-single-character-from-the-user

    data = ""

    while (data_waiting_on_stdin()):
        try:
            ch = sys.stdin.read(1)
            data += ch
        except IOError:
            break

    if (len(data) > 0):
        shell.sendall(data)

    return data


def data_waiting_on_stdin():
    # https://stackoverflow.com/questions/3762881/how-do-i-check-if-stdin-has-some-data
    return data_waiting(sys.stdin)


def data_waiting(descriptor):
    if select.select([descriptor, ], [], [], 0.0)[0]:
        return True
    else:
        return False


def receive_stdout():
    return receive(sys.stdout)


def receive_stderr():
    return receive(sys.stderr)


def receive(descriptor):
    # Create a new receive buffer
    receive_buffer = ""

    try:
        # Flush the receive buffer
        if (descriptor == sys.stdout):
            receive_buffer += shell.recv(buffer_size)
        elif (descriptor == sys.stderr):
            receive_buffer += shell.recv_stderr(buffer_size)
    except socket.timeout:
        return receive_buffer

    if (len(receive_buffer) == 0):
        # Channel stream has closed - http://www.lag.net/paramiko/docs/paramiko.Channel-class.html#recv
        return None
    else:
        return receive_buffer

# Get the command-line arguments
server_ip_address, username, password = pyuda.get_command_line_arguments(["Server IP address", "Username", "Password"])

if (len(sys.argv) == 5):
    port = sys.argv[4]
else:
    port = 22

# Create an SSH client
client = paramiko.SSHClient()

# Make sure that we add the remote server's SSH key automatically
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Connect to the client
client.connect(server_ip_address, port=port, username=username, password=password, allow_agent=False,
               look_for_keys=False)

# Create a raw shell
shell = client.invoke_shell()

# Set the timeout to 100 milliseconds
shell.settimeout(0.01)

old_settings = enter_raw_terminal_mode()

while (True):
    stdout_data = receive_stdout()
    if stdout_data is None: break

    if (len(stdout_data) == 0):
        time.sleep(0.1)
    else:
        sys.stdout.write(stdout_data)

    stderr_data = receive_stderr()
    if stderr_data is None: break

    if (len(stderr_data) == 0):
        time.sleep(0.1)
    else:
        sys.stdout.write(stderr_data)

    if (data_waiting_on_stdin()):
        send_stdin_data()

exit_raw_terminal_mode(old_settings)

# Close the SSH connection
client.close()
