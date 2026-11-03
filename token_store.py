"""Protect the Hugging Face token using the current Windows user's DPAPI key."""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path


class _Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]


def _protect(data, decrypt=False):
    if os.name != 'nt':
        raise OSError('Token storage requires Windows.')
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    source = ctypes.create_string_buffer(data)
    incoming = _Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    outgoing = _Blob()
    if decrypt:
        func = crypt32.CryptUnprotectData
        func.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        ok = func(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing))
    else:
        func = crypt32.CryptProtectData
        func.argtypes = [ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        ok = func(ctypes.byref(incoming), 'MangoFlux Hugging Face token', None, None, None, 1, ctypes.byref(outgoing))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel32.LocalFree(ctypes.cast(outgoing.data, ctypes.c_void_p))


def save(path, token):
    path = Path(path)
    encrypted = _protect(token.encode('utf-8'))
    temporary = path.with_suffix('.tmp')
    try:
        temporary.write_bytes(encrypted)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load(path):
    path = Path(path)
    return _protect(path.read_bytes(), decrypt=True).decode('utf-8') if path.exists() else ''


def forget(path):
    Path(path).unlink(missing_ok=True)
