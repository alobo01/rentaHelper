# file: fincli/cli.py
from __future__ import annotations
import argparse
import importlib
import yaml
from pathlib import Path
from typing import Any
import copy 
from .models import *
from .parsers import AbstractParser
from .processors import AbstractProcessor
from .output import AbstractOutputPipe


def _import(name: str) -> Any:
    module_name, _, class_name = name.rpartition(".")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def run(cfg_path: str | Path):
    cfg = yaml.safe_load(Path(cfg_path).read_text())

    # 1. instantiate parsers
    raw_results: list[RawDataOut] = []
    dataframes = []
    for p_conf in cfg["parsers"]:
        parser_cls: type[AbstractParser] = _import(p_conf["type"])
        config_cls = parser_cls.config_model
        config_obj = config_cls(**p_conf.get("params", {}))
        parser = parser_cls(config_obj)

        df = parser.load()
        dataframes.append(df)

        # gather raw ops
        raw_copy = copy.deepcopy(df["__object__"].tolist())
        raw_results.append(
            RawDataOut(
                parser_name=p_conf.get("name", parser_cls.__name__),
                records = raw_copy
            )
        )

    # 2. merge all FinOps
    all_ops = []
    for df in dataframes:
        all_ops.extend(df["__object__"].tolist())

    # 3. processors
    results = []
    for pr_conf in cfg["processors"]:
        proc_cls: type[AbstractProcessor] = _import(pr_conf["type"])
        processor = proc_cls(**pr_conf.get("params", {}))
        in_model = proc_cls.input_model(operations=all_ops)
        results.append(processor.process(in_model))

    # 4. output
    out_conf = cfg["output"]
    out_cls: type[AbstractOutputPipe] = _import(out_conf["type"])
    out_pipe = out_cls(**out_conf.get("params", {}))
    dst = out_pipe.render(*raw_results, *results)
    print(f"✅  Report generated at {dst}")

def main():
    ap = argparse.ArgumentParser(description="Financial CSV CLI")
    ap.add_argument("--config", default="config.yaml", help="YAML config file")
    args = ap.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
