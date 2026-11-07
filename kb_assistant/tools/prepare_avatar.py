#!/usr/bin/env python
"""
把角色三视图精灵图裁成小助手用的头像。

【为什么自己实现 PNG 解码】
    这个脚本只依赖标准库（zlib + struct）。
    装 Pillow 要联网，而这个项目在某些网络环境下装包很慢甚至装不上；
    PNG 的解码其实不复杂：拆 chunk -> 解压 IDAT -> 逐行反滤波。
    这样这个脚本在任何机器上都能直接跑。

【用法】
    python kb_assistant/tools/prepare_avatar.py <源图> <输出图> [x y w h] [目标边长]

    例：
        python kb_assistant/tools/prepare_avatar.py sprite.png kb.png 46 186 118 118 256

【支持的 PNG】
    位深 8，非隔行，颜色类型 0/2/3/4/6（灰度 / RGB / 调色板 / 灰度+透明 / RGBA）。
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


# ---------------------------------------------------------------------------
# 解码
# ---------------------------------------------------------------------------
def read_png(path: Path) -> tuple[int, int, bytes, int]:
    """
    读一个 PNG。

    返回 (width, height, pixel_data, channels)
    pixel_data 是「每行 row_bytes 个字节、逐行排列」的原始像素（已去掉滤波）。
    """
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError('不是合法的 PNG 文件')

    pos = len(PNG_SIGNATURE)
    width = height = 0
    bit_depth = color_type = interlace = 0
    idat = bytearray()
    palette = b''
    trns = b''

    while pos < len(data):
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length  # length(4) + type(4) + data + crc(4)

        if ctype == b'IHDR':
            width, height, bit_depth, color_type, _comp, _filt, interlace = struct.unpack(
                '>IIBBBBB', chunk
            )
        elif ctype == b'PLTE':
            palette = chunk
        elif ctype == b'tRNS':
            trns = chunk
        elif ctype == b'IDAT':
            idat += chunk
        elif ctype == b'IEND':
            break

    if bit_depth != 8:
        raise ValueError(f'只支持 8 位深度的 PNG，当前是 {bit_depth}')
    if interlace != 0:
        raise ValueError('不支持隔行 PNG')

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError(f'不支持的颜色类型：{color_type}')

    raw = zlib.decompress(bytes(idat))
    row_bytes = width * channels

    # 调色板图：展开成 RGB(A)
    if color_type == 3:
        out = bytearray()
        for y in range(height):
            start = y * (row_bytes + 1)
            for x in range(width):
                idx = raw[start + 1 + x]
                out += palette[idx * 3:idx * 3 + 3]
                if idx < len(trns):
                    out.append(trns[idx])
                else:
                    out.append(255)
        if len(trns) == 0:
            # 没有 tRNS 就补一条全不透明的 alpha
            out = bytearray()
            for y in range(height):
                start = y * (row_bytes + 1)
                for x in range(width):
                    idx = raw[start + 1 + x]
                    out += palette[idx * 3:idx * 3 + 3]
                    out.append(255)
        return width, height, bytes(out), 4

    # 反滤波
    out = bytearray(height * row_bytes)
    prev_row = bytearray(row_bytes)
    pos = 0
    for y in range(height):
        filter_type = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + row_bytes])
        pos += row_bytes

        if filter_type == 1:  # Sub
            for i in range(channels, row_bytes):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(row_bytes):
                line[i] = (line[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(row_bytes):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev_row[i]) >> 1)) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(row_bytes):
                left = line[i - channels] if i >= channels else 0
                up = prev_row[i]
                upper_left = prev_row[i - channels] if i >= channels else 0
                p = left + up - upper_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - upper_left)
                if pa <= pb and pa <= pc:
                    pred = left
                elif pb <= pc:
                    pred = up
                else:
                    pred = upper_left
                line[i] = (line[i] + pred) & 0xFF
        # filter_type == 0 (None) 不用处理

        out[y * row_bytes:(y + 1) * row_bytes] = line
        prev_row = line

    return width, height, bytes(out), channels


# ---------------------------------------------------------------------------
# 编码
# ---------------------------------------------------------------------------
def write_png(path: Path, width: int, height: int, pixels: bytes, channels: int) -> None:
    """写一个 PNG（颜色类型 6 = RGBA，每行滤波方式 0）。"""
    color_type = {1: 0, 2: 4, 3: 2, 4: 6}[channels]

    raw = bytearray()
    row_bytes = width * channels
    for y in range(height):
        raw.append(0)  # filter: None
        raw += pixels[y * row_bytes:(y + 1) * row_bytes]

    def chunk(ctype: bytes, payload: bytes) -> bytes:
        return (
            struct.pack('>I', len(payload))
            + ctype
            + payload
            + struct.pack('>I', zlib.crc32(ctype + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack('>IIBBBBB', width, height, 8, color_type, 0, 0, 0)
    body = (
        PNG_SIGNATURE
        + chunk(b'IHDR', ihdr)
        + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
        + chunk(b'IEND', b'')
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


# ---------------------------------------------------------------------------
# 裁剪 + 缩放
# ---------------------------------------------------------------------------
def crop(pixels: bytes, width: int, height: int, channels: int,
         box: tuple[int, int, int, int]) -> tuple[bytes, int, int]:
    """按 (x, y, w, h) 裁剪。"""
    x, y, w, h = box
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))

    out = bytearray()
    for row in range(y, y + h):
        start = (row * width + x) * channels
        out += pixels[start:start + w * channels]
    return bytes(out), w, h


def resize_bilinear(pixels: bytes, width: int, height: int, channels: int,
                    target: int) -> tuple[bytes, int, int]:
    """
    双线性缩放到 target x target。

    对头像这种小图来说，双线性比最近邻平滑很多，放大后不会发硬。
    """
    out = bytearray(target * target * channels)
    for y in range(target):
        # 采样点的中心对齐，避免整体偏移半个像素
        sy = (y + 0.5) * height / target - 0.5
        y0 = int(max(0, min(height - 1, int(sy))))
        y1 = int(max(0, min(height - 1, y0 + 1)))
        wy = sy - int(sy)
        if wy < 0:
            wy = 0.0

        for x in range(target):
            sx = (x + 0.5) * width / target - 0.5
            x0 = int(max(0, min(width - 1, int(sx))))
            x1 = int(max(0, min(width - 1, x0 + 1)))
            wx = sx - int(sx)
            if wx < 0:
                wx = 0.0

            for c in range(channels):
                p00 = pixels[(y0 * width + x0) * channels + c]
                p01 = pixels[(y0 * width + x1) * channels + c]
                p10 = pixels[(y1 * width + x0) * channels + c]
                p11 = pixels[(y1 * width + x1) * channels + c]

                top = p00 + (p01 - p00) * wx
                bottom = p10 + (p11 - p10) * wx
                value = top + (bottom - top) * wy
                out[(y * target + x) * channels + c] = max(0, min(255, int(round(value))))

    return bytes(out), target, target


def to_rgba(pixels: bytes, channels: int) -> bytes:
    """把任意通道数统一成 RGBA。"""
    if channels == 4:
        return pixels
    out = bytearray(len(pixels) // channels * 4)
    src = pixels
    for i in range(len(pixels) // channels):
        if channels == 3:
            out[i * 4:i * 4 + 4] = src[i * 3:i * 3 + 3] + b'\xff'
        elif channels == 1:
            v = src[i]
            out[i * 4:i * 4 + 4] = bytes((v, v, v, 255))
        elif channels == 2:
            v = src[i * 2]
            out[i * 4:i * 4 + 4] = bytes((v, v, v, src[i * 2 + 1]))
    return bytes(out)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    width, height, pixels, channels = read_png(src)
    print(f'[源图] {width} x {height}, 通道 {channels}')

    rgba = to_rgba(pixels, channels)
    cw, ch = width, height

    if len(sys.argv) >= 7:
        x, y, w, h = (int(v) for v in sys.argv[3:7])
        rgba, cw, ch = crop(rgba, width, height, 4, (x, y, w, h))
        print(f'[裁剪] -> {cw} x {ch}')

    rw, rh = cw, ch
    target = int(sys.argv[7]) if len(sys.argv) >= 8 else 0
    if target > 0:
        rgba, rw, rh = resize_bilinear(rgba, cw, ch, 4, target)
        print(f'[缩放] -> {rw} x {rh}')

    write_png(dst, rw, rh, rgba, 4)
    print(f'[输出] {dst}  ({rw} x {rh})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
