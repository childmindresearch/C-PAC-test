import json
import pathlib as pl
import sys
from typing import Literal
import yaml
import re
from typing import Any, Sequence


def filesafe(s: str, replacement: str = "-") -> str:
    """
    Converts a string to a file safe string.
    Removes all non-alphanumeric characters and
    replaces them with the replacement string.
    """
    return re.sub(r"[^\w\d-]", replacement, s).lower()


def multi_get(obj: dict, index: Sequence) -> Any | None:  # noqa: ANN401
    """
    Gets a value from a nested dictionary.
    Returns None if the path does not exist.
    """
    for i in index:
        if not isinstance(obj, dict) or i not in obj:
            return None
        obj = obj[i]
    return obj


def fetch_and_expand_cpac_configs(
    cpac_dir: pl.Path,
    output_dir: pl.Path,
    config_names_ids: dict[str, str],
) -> None:
    """
    Fetches C-PAC configs from github, fully expands them (FROM: parent),
    and then saves them to the specified directory.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    cpac_module_path = str(cpac_dir.absolute())

    if cpac_module_path not in sys.path:
        sys.path.append(cpac_module_path)

    from CPAC.utils.configuration.configuration import Preconfiguration  # noqa
    from CPAC.utils.configuration.yaml_template import create_yaml_from_template  # noqa

    for config_name, config_id in config_names_ids.items():
        conf = Preconfiguration(config_id)
        config_yaml_string = create_yaml_from_template(conf.dict(), "blank")

        with open(
            output_dir / (filesafe(config_name) + ".yml"), "w", encoding="utf-8"
        ) as handle:
            handle.write(config_yaml_string)


def get_cpac_config_ids() -> list[str]:
    from CPAC.pipeline import ALL_PIPELINE_CONFIGS

    return ALL_PIPELINE_CONFIGS


def fetch_and_expand_all_cpac_configs(
    cpac_dir: pl.Path,
    output_dir: pl.Path,
):
    config_names_ids = {i: i for i in get_cpac_config_ids()}
    fetch_and_expand_cpac_configs(
        cpac_dir=cpac_dir,
        output_dir=output_dir,
        config_names_ids=config_names_ids,
    )


def _normalize_index_union(indices) -> list[list[str]]:
    if not indices:
        return []
    if isinstance(indices[0], list):
        return indices
    return [indices]


def normalize_index_union(indices) -> list[list[str]]:
    re = _normalize_index_union(indices)
    assert all(isinstance(item, list) for item in re)
    assert all(isinstance(i, str) for item in re for i in item)
    return re


if __name__ == "__main__":

    from CPAC.pipeline import ALL_PIPELINE_CONFIGS
    from CPAC.utils.configuration.configuration import Configuration, Preconfiguration

    with open("nodeblock_index.json") as f:
        nbs = json.load(f)
    configs: dict[str, Configuration] = {config: Preconfiguration(config, skip_env_check=True) for config in ALL_PIPELINE_CONFIGS}

    print(f"Found {len(configs)} pre-configs!")

    def _any_true_in_config(config, multi_index_union):
        for path in multi_index_union:
            if multi_get(config, path):
                return True
        return False

    for nb in nbs:
        nb_configs = normalize_index_union(nb["decorator_args"].get("config"))
        nb_switchs = normalize_index_union(nb["decorator_args"].get("switch"))

        # multiply

        if not nb_configs and not nb_switchs:
            continue

        paths: list[list[str]] = []
        if not nb_configs:
            paths = nb_switchs
        else:
            for nb_config in nb_configs:
                for nb_switch in nb_switchs:
                    paths.append(nb_config + nb_switch)

        assert all(isinstance(item, list) for item in paths), paths
        assert all(isinstance(i, str) for item in paths for i in item), paths

        configs_with_this_enabled = []
        for config_name, config in configs.items():
            if all(config.switch_is_on(switch) for switch in paths):
                configs_with_this_enabled.append(config_name)

        nb["workflows"] = configs_with_this_enabled

    with open("nodeblock_index.json", "w", encoding="utf8") as handle:
        json.dump(nbs, handle, indent=2)
