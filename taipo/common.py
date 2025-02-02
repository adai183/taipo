import pathlib

import yaml
import pandas as pd
from clumper import Clumper
from parse import compile as parse_compile


def nlu_path_to_dataframe(path):
    """
    Converts a single nlu file with intents into a dataframe.
    Usage:
    ```python
    from taipo.common import nlu_path_to_dataframe
    df = nlu_path_to_dataframe("path/to/nlu/nlu.yml")
    ```
    """
    res = (
        Clumper.read_yaml(path)
        .explode("nlu")
        .keep(lambda d: "intent" in d["nlu"].keys())
        .mutate(
            examples=lambda d: d["nlu"]["examples"].split("\n"),
            intent=lambda d: d["nlu"]["intent"],
        )
        .drop("nlu", "version")
        .explode(text="examples")
        .mutate(text=lambda d: d["text"][2:])
        .keep(lambda d: d["text"] != "")
        .collect()
    )
    return pd.DataFrame(res)


def dataframe_to_nlu_file(dataf, write_path, text_col="text", label_col="intent"):
    """
    Converts a single DataFrame file with intents into a intents file for Rasa.
    Note that you cannot use this method to add entities.

    Usage:

    ```python
    import pandas as pd
    from taipo.common import dataframe_to_nlu_file
    df = pd.DataFrame([
        {"text": "i really really like this", "intent": "positive"},
        {"text": "i enjoy this", "intent": "positive"},
        {"text": "this is not my thing", "intent": "negative"}
    ])
    dataframe_to_nlu_file(df, write_path="path/to/nlu.yml")
    ```

    This will yield a file with the following contents:

    ```yaml
    version: 2.0
    nlu:
    - intent: negative
      examples: |
      - this is not my thing
    - intent: positive
      examples: |
      - i really really like this
      - i enjoy this
    ```
    """
    result = {"version": str(2.0), "nlu": []}
    for idx, group in dataf.groupby(label_col):
        intent = group[label_col].iloc[0]
        result["nlu"].append(
            {
                "intent": intent,
                "examples": [t for t in group[text_col]],
            }
        )
    dump = (
        yaml.dump(result, sort_keys=False, width=1000, allow_unicode=True)
        .replace("examples:", "examples: |")
        .replace("  -", "   -")
    )
    return pathlib.Path(write_path).write_text(dump)


def entity_names(rasa_strings):
    """
    Finds all entities in a sequence of Rasa style NLU strings.

    Usage:

    ```python
    out = entity_names("[python](proglang) and [pandas](package)")
    assert out == ["proglang", "package"]
    ```
    """
    r = parse_compile("({entity})")
    results = [list(r.findall(s)) for s in rasa_strings]
    flat_results = [item for sublist in results for item in sublist]
    if len(flat_results) == 0:
        return []
    uniq = pd.DataFrame([_.named for _ in flat_results])["entity"].unique()
    return list(uniq)


def gen_curly_ents(text):
    """
    Returns a list of all the curly entity bits for a single text.
    """
    while text.find("[") != -1:
        sq1 = text.find("[")
        sq2 = text[sq1:].find("]")
        br1 = text[sq1 + sq2 :].find("{")
        br2 = text[sq1 + sq2 + br1 :].find("}")
        ent = text[sq1 : sq1 + sq2 + 1]
        curly_bit = text[sq1 + sq2 + br1 : sq1 + sq2 + br1 + br2 + 1]
        yield ent, curly_bit
        text = text[sq1 + sq2 + br1 + br2 :]


def curly_entity_items(texts):
    """
    Returns a list of all the curly entity bits for a list of texts.
    """
    results = []
    for text in texts:
        items = gen_curly_ents(text)
        for ent, curly in items:
            cleaned = (
                curly.replace(":", " ")
                .replace("{", "")
                .replace("}", "")
                .replace(",", " ")
                .split(" ")
            )
            for item in cleaned:
                if item != "":
                    results.append(item)
    return list(set(results))


def replace_ent_assignment(texts):
    """
    Takes in a list of strings, possibly with entity annotations, and
    returns a list of strings without entity annotations.
    """
    parser = parse_compile("[{entity}]({ent_name})")
    results = []
    for t in texts:
        for found in [_.named for _ in parser.findall(t)]:
            t = t.replace(f"[{found['entity']}]", found["entity"])
            t = t.replace(f"({found['ent_name']})", "")
        results.append(t)
    return results
