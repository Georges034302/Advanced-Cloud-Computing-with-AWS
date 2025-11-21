#!/bin/bash
pkill -f gunicorn || true
systemctl stop nginx || true
