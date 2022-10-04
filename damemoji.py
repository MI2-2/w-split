# -*- coding:utf-8 -*-
# Windowsのファイル名ダメ文字を置換

def damemoji(s):
    dame = {':': '：', '/': '／', '\\': '', '?': '？', '"': '”', '<': '＜', '>': '＞', '*': '＊', '|': '｜'}
    dame_tbl = str.maketrans(dame)
    s = s.translate(dame_tbl)
    return s
