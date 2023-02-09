#!/usr/bin/env python3
import sys
from collections import defaultdict

import jieba
from jieba import posseg

STOP_FLAGS = [
    "d",  # 副词
    "f",  # 方位名词
    "x",  # 标点符号（文档说是 w 但是实际测试是 x
    "p",  # 介词
    "t",  # 时间
    "q",  # 量词
    "m",  # 数量词
    "nr",  # 人名，你我他
    "r",  # 代词
    "c",  # 连词
    "e",  # 文档没说，看着像语气词
    "xc",  # 其他虚词
    "zg",  # 文档没说，给出的词也没找到规律，但都不是想要的
    "y",  # 文档没说，看着像语气词
    # u 开头的都是助词，具体细分的分类文档没说
    "uj",
    "ug",
    "ul",
    "ud",
]

try:
    jieba.load_userdict("userdict.txt")
except:  # noqa: E722
    pass

result = defaultdict(int)

stopwords = set()

try:
    with open("StopWords-simple.txt") as f:
        for line in f:
            stopwords.add(line.strip())
except:  # noqa: E722
    pass

for line in sys.stdin:
    if line.startswith("/"):
        continue

    words = posseg.cut(line, HMM=True)

    for word, flag in words:
        if flag in STOP_FLAGS:
            continue
        if word.lower() in stopwords:
            continue
        result[word.lower()] += 1


for word, freq in result.items():
    print(f"{word}\t{freq}")
