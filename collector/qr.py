"""纯标准库 QR 码生成：byte 模式、EC=M、版本 1-6 自适应。见 SPEC.md「二维码」。

正确性以 python-qrcode 交叉比对录制的 fixture 快照锁定（tests/test_qr.py）。
matrix(text) 返回布尔方阵；rows(text) 返回 '1'/'0' 行字符串列表（嵌入 JSON 用）。
"""
from __future__ import annotations

# ---- 版本表（EC 级别 M）：{version: (每块 EC 码字数, [(块数, 每块数据码字数), ...])} ----
_VERSIONS = {
    1: (10, [(1, 16)]),
    2: (16, [(1, 28)]),
    3: (26, [(1, 44)]),
    4: (18, [(2, 32)]),
    5: (24, [(2, 43)]),
    6: (16, [(4, 27)]),
}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]}

# ---- GF(256) ----
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _rs_generator(n: int) -> list[int]:
    gen = [1]
    for i in range(n):
        gen = _poly_mul(gen, [1, _EXP[i]])
    return gen


def _poly_mul(a: list[int], b: list[int]) -> list[int]:
    result = [0] * (len(a) + len(b) - 1)
    for i, ca in enumerate(a):
        for j, cb in enumerate(b):
            if ca and cb:
                result[i + j] ^= _EXP[(_LOG[ca] + _LOG[cb]) % 255]
    return result


def _rs_encode(data: list[int], n_ec: int) -> list[int]:
    gen = _rs_generator(n_ec)
    rem = list(data) + [0] * n_ec
    for i in range(len(data)):
        factor = rem[i]
        if factor:
            for j in range(1, len(gen)):
                rem[i + j] ^= _EXP[(_LOG[gen[j]] + _LOG[factor]) % 255]
    return rem[len(data):]


# ---- 编码 ----

def _choose_version(n_bytes: int) -> int:
    for version, (_, blocks) in _VERSIONS.items():
        capacity = sum(cnt * size for cnt, size in blocks)
        # byte 模式头部：4 bit 模式 + 8 bit 长度（版本 1-9）
        if n_bytes <= capacity - 2:
            return version
    raise ValueError(f"内容过长（{n_bytes} 字节），超出版本 6-M 容量")


def _make_codewords(data: bytes, version: int) -> list[int]:
    ec_per_block, blocks = _VERSIONS[version]
    n_data = sum(cnt * size for cnt, size in blocks)

    bits: list[int] = []

    def put(value: int, length: int):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    put(0b0100, 4)
    put(len(data), 8)
    for byte in data:
        put(byte, 8)
    put(0, min(4, n_data * 8 - len(bits)))          # 终止符
    while len(bits) % 8:
        bits.append(0)
    codewords = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = (0xEC, 0x11)
    n_pads = 0
    while len(codewords) < n_data:
        codewords.append(pad[n_pads % 2])
        n_pads += 1

    # 分块 + RS + 交错
    data_blocks, pos = [], 0
    for cnt, size in blocks:
        for _ in range(cnt):
            data_blocks.append(codewords[pos:pos + size])
            pos += size
    ec_blocks = [_rs_encode(b, ec_per_block) for b in data_blocks]

    result = []
    for i in range(max(len(b) for b in data_blocks)):
        for b in data_blocks:
            if i < len(b):
                result.append(b[i])
    for i in range(ec_per_block):
        for b in ec_blocks:
            result.append(b[i])
    return result


# ---- 矩阵 ----

def _base_matrix(version: int):
    size = 17 + 4 * version
    grid = [[None] * size for _ in range(size)]         # None = 数据区

    def set_region(r0, c0, pattern):
        for dr, row in enumerate(pattern):
            for dc, val in enumerate(row):
                r, c = r0 + dr, c0 + dc
                if 0 <= r < size and 0 <= c < size:
                    grid[r][c] = bool(val)

    finder = [[1, 1, 1, 1, 1, 1, 1],
              [1, 0, 0, 0, 0, 0, 1],
              [1, 0, 1, 1, 1, 0, 1],
              [1, 0, 1, 1, 1, 0, 1],
              [1, 0, 1, 1, 1, 0, 1],
              [1, 0, 0, 0, 0, 0, 1],
              [1, 1, 1, 1, 1, 1, 1]]
    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        set_region(r0, c0, finder)
    # 分隔带
    for i in range(8):
        for r, c in ((7, i), (i, 7), (7, size - 8 + i), (i, size - 8),
                     (size - 8, i), (size - 8 + i, 7)):
            if 0 <= r < size and 0 <= c < size and grid[r][c] is None:
                grid[r][c] = False
    # 时序图案
    for i in range(8, size - 8):
        grid[6][i] = (i % 2 == 0)
        grid[i][6] = (i % 2 == 0)
    # 对齐图案
    align = [[1, 1, 1, 1, 1],
             [1, 0, 0, 0, 1],
             [1, 0, 1, 0, 1],
             [1, 0, 0, 0, 1],
             [1, 1, 1, 1, 1]]
    coords = _ALIGN[version]
    for r in coords:
        for c in coords:
            if grid[r][c] is None:                       # 跳过与定位符重叠的位置
                set_region(r - 2, c - 2, align)
    # 暗模块
    grid[size - 8][8] = True
    # 预留格式信息位（值稍后写入）
    for i in range(9):
        if grid[8][i] is None:
            grid[8][i] = False
        if grid[i][8] is None:
            grid[i][8] = False
    for i in range(8):
        if grid[8][size - 1 - i] is None:
            grid[8][size - 1 - i] = False
        if grid[size - 1 - i][8] is None:
            grid[size - 1 - i][8] = False
    return grid


def _data_positions(grid) -> list[tuple[int, int]]:
    """蛇形填充顺序（右下起，两列一组向左，跳过第 6 列时序线）。"""
    size = len(grid)
    positions = []
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for c in (col, col - 1):
                if grid[r][c] is None:
                    positions.append((r, c))
        upward = not upward
        col -= 2
    return positions


_MASKS = (
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
)


def _penalty(m) -> int:
    """掩码惩罚分。与 python-qrcode 的 lost_point 逐条对齐（含其 N3 跳跃扫描），
    以保证掩码选择一致、快照可交叉验证。"""
    size = len(m)
    score = 0
    lines = [[m[r][c] for c in range(size)] for r in range(size)] + \
            [[m[r][c] for r in range(size)] for c in range(size)]
    for line in lines:                                   # N1 连续同色（≥5 记 长度-2）
        run, prev = 0, None
        for val in line + [None]:
            if val == prev:
                run += 1
            else:
                if prev is not None and run >= 5:
                    score += run - 2
                run, prev = 1, val
    for r in range(size - 1):                            # N2 2x2 同色
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    bad = ([True, False, True, True, True, False, True, False, False, False, False],
           [False, False, False, False, True, False, True, True, True, False, True])
    for line in lines:                                   # N3 类定位符图案（带跳跃扫描）
        it = iter(range(len(line) - 10))
        for i in it:
            if line[i:i + 11] in bad:
                score += 40
            if line[i + 10]:
                next(it, None)
    dark = sum(sum(row) for row in m)                    # N4 明暗比例
    score += 10 * int(abs(dark * 100 / (size * size) - 50) / 5)
    return score


_FORMAT_MASK = 0b101010000010010
_EC_M_BITS = 0b00


def _format_bits(mask_id: int) -> int:
    data = (_EC_M_BITS << 3) | mask_id
    rem = data << 10
    gen = 0b10100110111
    for i in range(14, 9, -1):
        if rem >> i & 1:
            rem ^= gen << (i - 10)
    return ((data << 10) | rem) ^ _FORMAT_MASK


def _write_format(m, mask_id: int):
    size = len(m)
    bits = _format_bits(mask_id)
    get = lambda i: bool(bits >> (14 - i) & 1)
    # 左上副本
    coords_a = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
                (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    # 右上 + 左下副本
    coords_b = [(size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8),
                (size - 5, 8), (size - 6, 8), (size - 7, 8),
                (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5),
                (8, size - 4), (8, size - 3), (8, size - 2), (8, size - 1)]
    for i, (r, c) in enumerate(coords_a):
        m[r][c] = get(i)
    for i, (r, c) in enumerate(coords_b):
        m[r][c] = get(i)


def matrix(text: str) -> list[list[bool]]:
    data = text.encode("utf-8")
    version = _choose_version(len(data))
    codewords = _make_codewords(data, version)

    grid = _base_matrix(version)
    positions = _data_positions(grid)
    bits = [(cw >> (7 - i)) & 1 for cw in codewords for i in range(8)]
    bits.extend([0] * (len(positions) - len(bits)))      # 剩余位补 0

    # 与参照实现一致：评估掩码时格式位区域留白（False），选定后再写入格式信息
    best, best_id, best_score = None, None, None
    for mask_id, mask in enumerate(_MASKS):
        m = [row[:] for row in grid]
        for (r, c), bit in zip(positions, bits):
            m[r][c] = bool(bit) ^ mask(r, c)
        score = _penalty(m)
        if best_score is None or score < best_score:
            best, best_id, best_score = m, mask_id, score
    _write_format(best, best_id)
    return best


def rows(text: str) -> list[str]:
    return ["".join("1" if v else "0" for v in row) for row in matrix(text)]
