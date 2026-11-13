"""Miniatures natives Windows (celles de l'Explorateur) via IShellItemImageFactory, mises en cache sur disque."""
import ctypes
import hashlib
import threading
from ctypes import wintypes
from pathlib import Path

from PIL import Image

ole32 = ctypes.OleDLL("ole32")
shell32 = ctypes.OleDLL("shell32")
gdi32 = ctypes.WinDLL("gdi32")

SIIGBF_RESIZETOFIT = 0x00
SIIGBF_BIGGERSIZEOK = 0x01
SIIGBF_THUMBNAILONLY = 0x08   # pas d'icône générique : le front affiche sa propre icône par extension
COINIT_APARTMENTTHREADED = 0x2
RPC_E_CHANGED_MODE = -2147417850


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, text: str):
        super().__init__()
        ole32.CLSIDFromString(text, ctypes.byref(self))


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BITMAP(ctypes.Structure):
    _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long), ("bmHeight", ctypes.c_long),
                ("bmWidthBytes", ctypes.c_long), ("bmPlanes", wintypes.WORD), ("bmBitsPixel", wintypes.WORD),
                ("bmBits", ctypes.c_void_p)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


IID_IShellItemImageFactory = GUID("{bcc18b79-ba16-442f-80c4-8a59c30c463b}")
GetImageProto = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, SIZE, ctypes.c_int, ctypes.POINTER(wintypes.HBITMAP))
ReleaseProto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)

shell32.SHCreateItemFromParsingName.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]

_local = threading.local()


def _com_init():
    if getattr(_local, "ready", False):
        return
    try:
        ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    except OSError as e:
        if e.winerror != RPC_E_CHANGED_MODE:  # thread déjà initialisé autrement : ça marche quand même
            raise
    _local.ready = True


def _hbitmap_to_image(hbm) -> Image.Image:
    bmp = BITMAP()
    gdi32.GetObjectW(hbm, ctypes.sizeof(bmp), ctypes.byref(bmp))
    w, h = bmp.bmWidth, bmp.bmHeight
    header = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
    buf = ctypes.create_string_buffer(w * h * 4)
    hdc = gdi32.CreateCompatibleDC(None)
    try:
        gdi32.GetDIBits(hdc, hbm, 0, h, buf, ctypes.byref(header), 0)
    finally:
        gdi32.DeleteDC(hdc)
    img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1)
    if img.getchannel("A").getextrema() == (0, 0):  # bitmap sans canal alpha : opaque
        img = img.convert("RGB")
    return img


def shell_thumbnail(path: str, size: int) -> Image.Image | None:
    _com_init()
    factory = ctypes.c_void_p()
    try:
        shell32.SHCreateItemFromParsingName(path, None, ctypes.byref(IID_IShellItemImageFactory), ctypes.byref(factory))
    except OSError:
        return None
    vtable = ctypes.cast(ctypes.cast(factory, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    get_image = GetImageProto(vtable[3])
    release = ReleaseProto(vtable[2])
    hbm = wintypes.HBITMAP()
    try:
        get_image(factory, SIZE(size, size), SIIGBF_THUMBNAILONLY | SIIGBF_BIGGERSIZEOK, ctypes.byref(hbm))
        return _hbitmap_to_image(hbm)
    except OSError:
        return None
    finally:
        if hbm:
            gdi32.DeleteObject(hbm)
        release(factory)


class ThumbCache:
    def __init__(self, cache_dir: Path):
        self.dir = cache_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def get(self, path: str, size_bytes: int, mtime: float, px: int) -> Path | None:
        key = hashlib.sha1(f"{path}|{size_bytes}|{mtime}|{px}".encode("utf-8")).hexdigest()
        out = self.dir / f"{key}.webp"
        miss = self.dir / f"{key}.none"
        if out.exists():
            return out
        if miss.exists():
            return None
        img = shell_thumbnail(path, px)
        self.dir.mkdir(parents=True, exist_ok=True)  # le cache a pu être vidé pendant que l'appli tourne
        if img is None:
            miss.touch()
            return None
        img.thumbnail((px, px))
        img.save(out, "WEBP", quality=82)
        return out
