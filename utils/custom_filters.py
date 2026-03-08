# Copyright (c) 2026 TeamJB
# Repository: https://github.com/teamjb1/teamjassbeniwal-ctrl
# Licensed under the GNU General Public License v3.0.

from pyrogram import filters

user_steps = {}

def login_filter_func(_, __, message):
    user_id = message.from_user.id
    return user_id in user_steps

login_in_progress = filters.create(login_filter_func)

def set_user_step(user_id, step=None):
    if step:
        user_steps[user_id] = step
    else:
        user_steps.pop(user_id, None)


def get_user_step(user_id):
    return user_steps.get(user_id)
