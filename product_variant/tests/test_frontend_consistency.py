# -*- coding: utf-8 -*-
"""前端资源的静态一致性检查（不需要浏览器）。

这一组检查覆盖「服务端测试抓不到、但一崩就整页打不开」的两类错误（都实测踩过，
案例见模块 ``AGENTS.md`` → L2 P4 陷阱 8 / 陷阱 9）：

1. **字段 widget 必须注册成描述对象**：``registry.category("fields").add("x", X)`` 里的 ``X``
   得是 ``{component: ..., displayName: ...}`` 对象。注册裸组件类时 ``web.Field`` 拿到的
   ``field.component`` 是 ``undefined``，渲染直接崩在 ``Component.name``（报错栈只指到
   ``Field.template``，完全不提本模块）。
2. **模板表达式引用的名字必须在组件实例上真实存在**：OWL 模板里 ``state`` 不是保留字，
   写 ``state.blocked`` 只会得到 ``undefined.blocked``；报错栈指向模板函数名。

检查都是纯文本扫描，没有浏览器依赖，所以能进常规的 ``task test``。
"""

import re
from pathlib import Path

from odoo.tests.common import TransactionCase

# OWL 模板里可以不经组件实例访问的名字
TEMPLATE_BUILTINS = {"props", "this", "true", "false", "null", "undefined"}

# 组件成员的定义形态
JS_MEMBER_PATTERNS = (
    r"get\s+([A-Za-z_$][\w$]*)\s*\(",  # get xxx()
    r"^\s{4}([A-Za-z_$][\w$]*)\s*\(",  # 方法 xxx()
    r"this\.([A-Za-z_$][\w$]*)\s*=",  # setup 里的属性
)


class TestFrontendConsistency(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(__file__).resolve().parents[1]
        cls.js_paths = sorted((root / "static" / "src" / "js").glob("*.js"))
        cls.xml_paths = sorted((root / "static" / "src" / "xml").glob("*.xml"))
        cls.js_texts = {path: path.read_text(encoding="utf-8") for path in cls.js_paths}
        cls.xml_texts = {path: path.read_text(encoding="utf-8") for path in cls.xml_paths}

    def test_assets_are_registered_in_manifest(self):
        """static/src 下的每个 js / xml 都要登记进 manifest 的 assets，否则 -u 也不会加载。"""
        manifest = (Path(__file__).resolve().parents[1] / "__manifest__.py").read_text(encoding="utf-8")
        for path in list(self.js_paths) + list(self.xml_paths):
            self.assertIn(
                str(path).split("product_variant/")[-1],
                manifest,
                "前端文件 %s 没有登记进 __manifest__.py 的 assets" % path.name,
            )

    def test_field_widget_registered_as_descriptor(self):
        """字段注册表的值必须是 {component: ...} 描述对象，不能是裸标识符（陷阱 8）。"""
        call_re = re.compile(
            r'registry\.category\("fields"\)\.add\(\s*"([^"]+)"\s*,\s*([^)]+?)\s*\)\s*;'
        )
        checked = 0
        for path, text in self.js_texts.items():
            for key, registered in call_re.findall(text):
                checked += 1
                if registered.startswith("{"):
                    # 内联对象字面量：确认里面有 component
                    self.assertIn(
                        "component",
                        registered,
                        "%s: 字段 %s 的注册对象里缺少 component" % (path.name, key),
                    )
                    continue
                # 注册的是标识符：它必须在同一文件里被定义成对象字面量
                self.assertRegex(
                    text,
                    r"(?:const|let|var)\s+%s\s*=\s*\{" % re.escape(registered),
                    "%s: 字段 %s 注册的是 %s，必须是 {component: ...} 描述对象（见 AGENTS.md → "
                    "L2 P4 陷阱 8：注册裸类会让 web.Field 拿到 undefined 的 component）"
                    % (path.name, key, registered),
                )
        self.assertTrue(checked, "没有扫到任何字段 widget 注册，检查可能失效了")

    def test_template_expressions_resolve_on_component(self):
        """模板里的每个名字都要能在组件上找到（陷阱 9：state 不是 OWL 保留字）。"""
        members = set()
        for text in self.js_texts.values():
            for pattern in JS_MEMBER_PATTERNS:
                members.update(re.findall(pattern, text, re.M))

        expr_attrs = r't-(?:esc|if|elif|foreach|key|att-[\w-]+|on-[\w-]+)="([^"]*)"'
        root_re = re.compile(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*(?=[.(\[])")
        checked = 0
        for path, text in self.xml_texts.items():
            # t-foreach / t-as 引入的循环变量（含 _index / _value / _first / _last）
            loop_vars = set()
            for var in re.findall(r't-as="([^"]+)"', text):
                loop_vars |= {var, var + "_index", var + "_value", var + "_first", var + "_last"}
            allowed = TEMPLATE_BUILTINS | loop_vars
            for expression in re.findall(expr_attrs, text):
                for name in root_re.findall(expression):
                    checked += 1
                    self.assertIn(
                        name,
                        members | allowed,
                        "%s: 模板表达式里的 %r 在组件上不存在（表达式：%s）—— 模板只能引用组件实例上的 "
                        "getter / 方法 / 属性，或 t-as 的循环变量；见 AGENTS.md → L2 P4 陷阱 9"
                        % (path.name, name, expression),
                    )
        self.assertTrue(checked, "没有扫到任何模板表达式，检查可能失效了")

    def test_template_names_match_component_template(self):
        """xml 里的 t-name 必须与组件 static template 一一对应。"""
        declared = set(re.findall(r't-name="([^"]+)"', "".join(self.xml_texts.values())))
        used = set()
        for text in self.js_texts.values():
            used.update(re.findall(r'static\s+template\s*=\s*"([^"]+)"', text))
        self.assertEqual(
            used - declared,
            set(),
            "组件引用的模板 %s 在 static/src/xml 里找不到" % sorted(used - declared),
        )
        self.assertEqual(
            declared - used,
            set(),
            "static/src/xml 里的模板 %s 没有组件引用" % sorted(declared - used),
        )
