# -*- coding:utf-8 -*-
# windows like sort (Windows only): https://qiita.com/dengax/items/d20deab8262d5fa4559d

def winsort(lst):
    import ctypes
    from functools import cmp_to_key

    SHLWAPI = ctypes.windll.LoadLibrary("SHLWAPI.dll")
    def cmpstr(a, b):
        return SHLWAPI.StrCmpLogicalW(a, b)

    return sorted(lst, key=cmp_to_key(cmpstr))
