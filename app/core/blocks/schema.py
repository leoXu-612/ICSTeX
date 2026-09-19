"""JSON Schema (Draft 2020-12) contracts for Blocks, layouts, and projects.

The schemas are the machine-verifiable protocol of the Block model: required
fields, types, enums, label patterns, and per-type content constraints. The
validator returns stable, testable issue strings.
"""
from __future__ import annotations

from jsonschema import Draft202012Validator

from app.core.blocks.model import BLOCK_TYPES, SCHEMA_VERSION


BLOCK_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://icstex.local/schema/block/1.0.0",
    "title": "ICSTeX Block",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schemaVersion",
        "id",
        "type",
        "alias",
        "semantic",
        "content",
        "references",
        "provenance",
        "revision",
    ],
    "properties": {
        "schemaVersion": {"const": SCHEMA_VERSION},
        "id": {"type": "string", "minLength": 4, "pattern": "^[a-z]+_[A-Z0-9]{26}$"},
        "type": {"enum": list(BLOCK_TYPES)},
        "alias": {"type": "string", "minLength": 1},
        "semantic": {
            "type": "object",
            "additionalProperties": False,
            "required": ["role"],
            "properties": {
                "role": {"type": "string", "minLength": 1},
                "label": {"type": ["string", "null"]},
                "caption": {
                    "type": ["object", "null"],
                    "additionalProperties": False,
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string"},
                        "shortText": {"type": ["string", "null"]},
                    },
                },
                "numbering": {"enum": ["auto", "none", "manual"]},
            },
        },
        "content": {"type": "object"},
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["targetBlockId"],
                "properties": {
                    "targetBlockId": {"type": "string"},
                    "kind": {
                        "enum": ["citation", "cross-reference", "dependency", "source"],
                    },
                    "display": {"enum": ["number", "name", "page", "custom", "null"]},
                    "customText": {"type": ["string", "null"]},
                },
            },
        },
        "provenance": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind"],
            "properties": {
                "kind": {"enum": ["created", "imported", "linked"]},
                "sourceId": {"type": ["string", "null"]},
                "importedAt": {"type": ["string", "null"]},
            },
        },
        "revision": {"type": "integer", "minimum": 1},
        "metadata": {"type": "object"},
        "extensions": {"type": "object"},
    },
}


CONTENT_SCHEMAS: dict[str, dict] = {
    "text": {
        "type": "object",
        "additionalProperties": False,
        "required": ["format", "text"],
        "properties": {
            "format": {"const": "plain"},
            "text": {"type": "string"},
        },
    },
    "heading": {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "level"],
        "properties": {
            "text": {"type": "string"},
            "level": {"type": "integer", "minimum": 1, "maximum": 6},
        },
    },
    "quote": {
        "type": "object",
        "additionalProperties": False,
        "required": ["text"],
        "properties": {"text": {"type": "string"}},
    },
    "list": {
        "type": "object",
        "additionalProperties": False,
        "required": ["ordered", "items"],
        "properties": {
            "ordered": {"type": "boolean"},
            "items": {"type": "array", "items": {"type": "string"}},
        },
    },
    "rawLatex": {
        "type": "object",
        "additionalProperties": False,
        "required": ["latex", "trusted"],
        "properties": {
            "latex": {"type": "string"},
            "trusted": {"type": "boolean"},
        },
    },
    "formula": {
        "type": "object",
        "additionalProperties": False,
        "required": ["format", "astVersion", "ast", "latexCache"],
        "properties": {
            "format": {"const": "icstex-formula-ast"},
            "astVersion": {"const": "1.0.0"},
            "ast": {"type": "object"},
            "latexCache": {"type": "string"},
        },
    },
    "image": {
        "type": "object",
        "additionalProperties": False,
        "required": ["source"],
        "properties": {
            "source": {"type": "string", "minLength": 1},
            "width": {"type": ["string", "null"]},
        },
    },
    "table": {
        "type": "object",
        "additionalProperties": False,
        "required": ["tableVersion", "columns", "rows", "header", "merges", "notes"],
        "properties": {
            "tableVersion": {"const": "1.0.0"},
            "columns": {"type": "array", "items": {"type": "object"}},
            "rows": {"type": "array", "items": {"type": "object"}},
            "header": {"type": "object"},
            "merges": {"type": "array", "items": {"type": "object"}},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    },
}


PROJECT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://icstex.local/schema/project/1.0.0",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "projectSchemaVersion",
        "minimumAppVersion",
        "blockSchemaVersion",
        "layoutSchemaVersion",
        "themeSchemaVersion",
    ],
    "properties": {
        "projectSchemaVersion": {"const": SCHEMA_VERSION},
        "minimumAppVersion": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "blockSchemaVersion": {"const": SCHEMA_VERSION},
        "layoutSchemaVersion": {"const": SCHEMA_VERSION},
        "themeSchemaVersion": {"const": SCHEMA_VERSION},
    },
}


LAYOUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://icstex.local/schema/layout/1.0.0",
    "type": "object",
    "additionalProperties": False,
    "required": ["schemaVersion", "id", "kind", "children"],
    "$defs": {
        "size": {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "unit"],
            "properties": {
                "value": {"type": "number", "minimum": 0},
                "unit": {"enum": ["mm", "pt"]},
            },
        },
        "slot": {
            "type": "object",
            "additionalProperties": False,
            "required": ["instanceId", "kind", "blockId"],
            "properties": {
                "instanceId": {"type": "string", "minLength": 4},
                "kind": {"const": "block"},
                "blockId": {"type": "string"},
                "weight": {"type": "number", "exclusiveMinimum": 0},
                "minWidthPt": {"type": ["number", "null"], "minimum": 0},
            },
        },
        "child": {
            "oneOf": [
                {"$ref": "#/$defs/slot"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["instanceId", "kind", "children"],
                    "properties": {
                        "instanceId": {"type": "string", "minLength": 4},
                        "kind": {"const": "container"},
                        "children": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/child"},
                        },
                    },
                },
            ]
        },
    },
    "properties": {
        "schemaVersion": {"const": SCHEMA_VERSION},
        "id": {"type": "string", "minLength": 4},
        "kind": {"enum": ["row", "column", "grid", "fullWidth"]},
        "columns": {"type": ["integer", "null"], "minimum": 1},
        "gap": {"$ref": "#/$defs/size"},
        "rowGap": {"$ref": "#/$defs/size"},
        "alignment": {"type": "string"},
        "keepTogether": {"enum": ["row", "grid", "none"]},
        "fallback": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strategy": {
                    "enum": ["reduceGap", "normalizeWeights", "wrapRows", "stackVertically", "error"],
                },
                "minimumChildWidthPt": {"type": "number", "minimum": 0},
                "stackGap": {"$ref": "#/$defs/size"},
            },
        },
        "children": {
            "type": "array",
            "items": {"$ref": "#/$defs/child"},
        },
    },
}


APP_THEME_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://icstex.local/schema/app-theme/1.0.0",
    "type": "object",
    "additionalProperties": False,
    "required": ["schemaVersion", "kind", "id", "name", "mode", "tokens", "typography", "effects"],
    "properties": {
        "schemaVersion": {"const": SCHEMA_VERSION},
        "kind": {"const": "app-theme"},
        "id": {"type": "string", "minLength": 4},
        "name": {"type": "string"},
        "mode": {"enum": ["light", "dark", "system"]},
        "tokens": {
            "type": "object",
            "required": [
                "background",
                "surface",
                "surfaceElevated",
                "foreground",
                "foregroundMuted",
                "border",
                "accent",
                "accentForeground",
                "selection",
                "success",
                "warning",
                "error",
                "layoutGuide",
            ],
        },
        "typography": {"type": "object"},
        "effects": {"type": "object"},
    },
}


DOCUMENT_THEME_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://icstex.local/schema/document-theme/1.0.0",
    "type": "object",
    "additionalProperties": False,
    "required": ["schemaVersion", "kind", "id", "name", "page", "typography"],
    "properties": {
        "schemaVersion": {"const": SCHEMA_VERSION},
        "kind": {"const": "document-theme"},
        "id": {"type": "string", "minLength": 4},
        "name": {"type": "string"},
        "page": {
            "type": "object",
            "required": ["size", "orientation", "columns", "margin"],
            "properties": {
                "size": {"enum": ["a4", "letter"]},
                "orientation": {"enum": ["portrait", "landscape"]},
                "columns": {"enum": [1, 2]},
                "margin": {"type": "object"},
            },
        },
        "typography": {
            "type": "object",
            "required": ["textFamily", "mathFamily", "monoFamily", "baseSizePt", "lineSpacing"],
        },
        "headings": {"type": "object"},
        "figures": {"type": "object"},
        "tables": {"type": "object"},
        "layout": {"type": "object"},
    },
}


SOURCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://icstex.local/schema/source/1.0.0",
    "type": "object",
    "additionalProperties": False,
    "required": ["sourceId", "kind", "relativePath", "baseSha256"],
    "properties": {
        "sourceId": {"type": "string", "minLength": 4},
        "kind": {"enum": ["csv", "xlsx", "clipboard", "linked"]},
        "relativePath": {"type": "string", "minLength": 1},
        "baseSha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "createdAt": {"type": ["string", "null"]},
    },
}


_VALIDATORS = {
    "block": Draft202012Validator(BLOCK_SCHEMA),
    "project": Draft202012Validator(PROJECT_SCHEMA),
    "layout": Draft202012Validator(LAYOUT_SCHEMA),
    "app-theme": Draft202012Validator(APP_THEME_SCHEMA),
    "document-theme": Draft202012Validator(DOCUMENT_THEME_SCHEMA),
    "source": Draft202012Validator(SOURCE_SCHEMA),
}
_CONTENT_VALIDATORS = {
    block_type: Draft202012Validator(schema) for block_type, schema in CONTENT_SCHEMAS.items()
}


def _issues(validator: Draft202012Validator, data: object) -> list[str]:
    return [
        f"{error.json_path or '#'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda error: error.json_path)
    ]


def validate_block(data: dict) -> list[str]:
    """Return stable issue strings for a Block dictionary (empty when valid)."""

    issues = _issues(_VALIDATORS["block"], data)
    if issues:
        return issues
    block_type = data["type"]
    content_issues = _issues(_CONTENT_VALIDATORS[block_type], data["content"])
    return issues + content_issues


def is_valid_block(data: dict) -> bool:
    return not validate_block(data)


def validate_project(data: dict) -> list[str]:
    return _issues(_VALIDATORS["project"], data)


def validate_layout(data: dict) -> list[str]:
    return _issues(_VALIDATORS["layout"], data)


def validate_theme(data: dict) -> list[str]:
    kind = data.get("kind")
    validator = _VALIDATORS.get(kind)
    if validator is None:
        return ["未知主题类型：" + str(kind)]
    return _issues(validator, data)


def validate_source(data: dict) -> list[str]:
    return _issues(_VALIDATORS["source"], data)
