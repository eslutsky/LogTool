#!/usr/bin/python
import os
os.system('sudo podman ps -a | grep -i exited > stam.txt')
os.system('cat stam.txt')