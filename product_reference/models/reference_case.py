# -*- coding: utf-8 -*-
"""型号类字段的大小写规范化：写入时一律转大写。

涉及的字段（见 ``UPPERCASE_FIELDS``）：
- 额外参考号 ``product.reference.code.reference_code``
- 产品编号 ``product.template.base_reference`` 与产品表单的 ``Ref.``
  （``product.template.default_code``）
- 变体编号 ``product.product.default_code``

为什么在 ``create`` / ``write`` 里改写 ``vals``，而不用 compute / onchange：
- 就地改写 vals **不产生额外写入**，不会像「顺手写另一个字段」那样触发反向同步成环
  （见模块 ``AGENTS.md`` → L2 P4）；
- 前端两个输入框（``Ref.`` 与额外参考号弹窗）在输入时即显示大写，后端这里是同一
  口径的兜底：导入 / API / 脚本 / 其它模块写入也一律大写。

只做大小写归一：不裁剪空格、不改其它字符。**存量数据不自动改写** —— 同一主人下
已有 ``abc`` 与 ``ABC`` 两行时，转大写会撞唯一约束，脚本无法替用户消歧；
需要时按 ``README.md`` 里的命令手工执行（会跳过撞约束的行）。
"""

# 各模型需要转大写的字段：改这里即可增删，三个模型的 create / write 都读它
UPPERCASE_FIELDS = {
    "product.reference.code": ("reference_code",),
    "product.template": ("base_reference", "default_code"),
    "product.product": ("default_code",),
}


def uppercase_reference_vals(vals, field_names):
    """把 ``vals`` 里指定字段的字符串值就地转为大写。

    空值（``False`` / ``None``）与非字符串原样跳过：``default_code`` 常被清成
    ``False``，``toUpper`` 之类的调用不能把它变成 ``"FALSE"``。
    """
    for name in field_names:
        value = vals.get(name)
        if isinstance(value, str):
            vals[name] = value.upper()
