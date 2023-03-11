import bitcoinformats.deconstruct as d


class Example(d.Struct):
    x: d.int16ul
    y: "d.int32ul"
    z: d.int64ul = d.field()

    def hello(self) -> None:
        print("hello", self.x)


def test_example():
    e = Example(x=1, y=2, z=3)
    assert e.x == 1
    assert e.y == 2
    assert e.z == 3
    assert e.build() == b"\x01\x00\x02\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00"
    assert (
        Example.parse(b"\x01\x00\x02\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00") == e
    )
    assert e.sizeof() == 2 + 4 + 8
