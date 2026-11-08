import unittest

from agent.policy import parse_action


class PolicyTests(unittest.TestCase):
    def test_click_normalized(self):
        action = parse_action({'type': 'click', 'x': 500, 'y': 300, 'button': 'left'})
        self.assertEqual(action.type, 'click')
        self.assertEqual(action.x, 500)

    def test_click_out_of_bounds(self):
        for x in (-1, 1001, 0.5, True):
            with self.subTest(x=x), self.assertRaises(ValueError):
                parse_action({'type': 'click', 'x': x, 'y': 100})

    def test_reject_shell(self):
        with self.assertRaises(ValueError):
            parse_action({'type': 'shell', 'command': 'dir'})

    def test_reject_long_text(self):
        with self.assertRaises(ValueError):
            parse_action({'type': 'type_text', 'text': 'x' * 241})

    def test_reject_windows_run(self):
        with self.assertRaises(ValueError):
            parse_action({'type': 'hotkey', 'keys': ['win', 'r']})

    def test_accept_save(self):
        self.assertEqual(parse_action({'type': 'hotkey', 'keys': ['ctrl', 's']}).keys,
                         ('ctrl', 's'))

    def test_reject_arbitrary_key(self):
        with self.assertRaises(ValueError):
            parse_action({'type': 'press_key', 'key': 'printscreen'})

    def test_reject_bad_scroll(self):
        with self.assertRaises(ValueError):
            parse_action({'type': 'scroll', 'amount': 100})

    def test_no_implicit_multiple_actions(self):
        with self.assertRaises(ValueError):
            parse_action([{'type': 'click', 'x': 0, 'y': 0}])


if __name__ == '__main__':
    unittest.main()
