from logic import calc_profit, parse_csv

def test_profit():
    assert calc_profit(300, 500, 50) == (150.0, 50.0)

def test_csv():
    rows = parse_csv(b"title,price,category\nTest,12.5,Digital\n")
    assert len(rows) == 1
    assert rows[0][2] == 12.5
