use jieba_rs::Jieba;
use std::collections::HashMap;
use std::io::{Result, Write};

fn main() -> Result<()> {
    let jieba = Jieba::new();
    let stdin = std::io::stdin();
    let mut result = HashMap::new();
    for line in stdin.lines() {
        match line {
            Ok(line) => {
                if line.is_empty() {
                    continue;
                }

                if line.starts_with('/') {
                    continue;
                }

                for tag in jieba.tag(&line, true) {
                    if STOP_FLAGS.contains(&tag.tag) || tag.word.len() > 21 {
                        continue;
                    }
                    result
                        .entry(tag.word.to_lowercase())
                        .and_modify(|c| *c += 1)
                        .or_insert(1);
                }
            }
            Err(_) => break,
        }
    }

    let stdout = std::io::stdout();
    let mut stdout = stdout.lock();
    for (k, v) in result {
        writeln!(stdout, "{}\t{}", k, v)?;
    }

    Ok(())
}

const STOP_FLAGS: &[&str] = &[
    "d",  // 副词
    "f",  // 方位名词
    "x",  // 标点符号（文档说是 w 但是实际测试是 x
    "p",  // 介词
    "t",  // 时间
    "q",  // 量词
    "m",  // 数量词
    "nr", // 人名，你我他
    "r",  // 代词
    "c",  // 连词
    "e",  // 文档没说，看着像语气词
    "xc", // 其他虚词
    "zg", // 文档没说，给出的词也没找到规律，但都不是想要的
    "y",  // 文档没说，看着像语气词
    // u 开头的都是助词，具体细分的分类文档没说
    "uj", "ug", "ul", "ud",
];
