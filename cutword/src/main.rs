use anyhow::{anyhow, Result};
use jieba_rs::Jieba;
use std::collections::HashMap;
use std::collections::HashSet;
use std::fs::File;
use std::io::{BufRead, BufReader, Write};

fn main() -> Result<()> {
    let mut jieba = Jieba::new();
    let stdin = std::io::stdin();
    let mut result = HashMap::new();
    let stderr = std::io::stderr();
    let mut stderr = stderr.lock();
    if let Err(e) = load_dict(&mut jieba) {
        writeln!(stderr, "Reading userdict.txt failed: {:#}", e)?;
    }
    let stopwords = match load_stopwords() {
        Ok(s) => s,
        Err(_) => HashSet::new(),
    };
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
                    let word = tag.word.to_lowercase();
                    if stopwords.contains(&word) {
                        continue;
                    }
                    result
                        .entry(word)
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

fn load_dict(jieba: &mut Jieba) -> Result<()> {
    let file = BufReader::new(File::open("userdict.txt")?);
    for line in file.lines() {
        match line {
            Ok(line) => {
                let mut it = line.split_whitespace();
                let word = it.next().ok_or_else(|| anyhow!("Bad line: {}", line))?;
                let tag = Some(it.next().ok_or_else(|| anyhow!("Bad line: {}", line))?);
                jieba.add_word(word, None, tag);
            }
            Err(_) => break,
        }
    }
    Ok(())
}

fn load_stopwords() -> Result<HashSet<String>> {
    let file = BufReader::new(File::open("StopWords-simple.txt")?);
    let mut result = HashSet::new();
    for line in file.lines() {
        match line {
            Ok(line) => {
                result.insert(line);
            }
            Err(_) => break,
        }
    }
    Ok(result)
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
