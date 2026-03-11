#!/bin/bash
# Extend the logical volume to use all free space

sudo lvextend -l +100%FREE -r /dev/mapper/ubuntu--vg-ubuntu--lv