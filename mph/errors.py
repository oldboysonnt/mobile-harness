"""Lỗi chuẩn của harness: mọi raise đều kèm hint cách sửa."""


class HarnessError(Exception):
    """Lỗi vận hành harness, `hint` chỉ cách khắc phục."""

    def __init__(self, msg: str, hint: str = "") -> None:
        super().__init__(msg if not hint else f"{msg} | hint: {hint}")
        self.hint = hint
