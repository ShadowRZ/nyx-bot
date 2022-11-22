import ast
import operator
import re
from random import randint
from re import Match

_OP_MAP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Invert: operator.neg,
}


class Calc(ast.NodeVisitor):
    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        return _OP_MAP[type(node.op)](left, right)

    def visit_Num(self, node):
        return node.n

    def visit_Expr(self, node):
        return self.visit(node.value)

    @classmethod
    def evaluate(cls, expression):
        tree = ast.parse(expression)
        calc = cls()
        return calc.visit(tree.body[0])


TRPG_PATTERN = re.compile("([0-9]+)[dD]([0-9]+)")


def get_trpg_dice_result(input: str) -> str:
    def dicer_(match: Match):
        count = int(match.group(1) or "1")
        num = int(match.group(2))
        ret = 0
        for _ in range(count):
            ret += randint(1, num)

        return str(ret)

    expr = TRPG_PATTERN.sub(dicer_, input)
    result = Calc.evaluate(expr)
    return result
