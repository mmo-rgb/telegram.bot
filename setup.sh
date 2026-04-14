#!/bin/bash
cd /root/radiance && git pull && pm2 start webhook.py --name webhook --interpreter python3 && pm2 restart radiance-bot && pm2 save && echo "OK"
