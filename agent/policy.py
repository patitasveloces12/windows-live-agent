"""Propuestas estructuradas; nunca ejecutamos código arbitrario generado por la IA."""
from dataclasses import dataclass


VALID_TYPES = {'move', 'click', 'scroll', 'type_text', 'press_key', 'hotkey'}
SAFE_KEYS = {
    'enter', 'tab', 'esc', 'escape', 'backspace', 'delete', 'space',
    'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
    'f2', 'f3', 'f5',
}
SAFE_HOTKEYS = {
    ('ctrl', 'a'), ('ctrl', 'c'), ('ctrl', 's'),
    ('ctrl', 'f'), ('ctrl', 'z'), ('ctrl', 'shift', 'z'),
    ('ctrl', 'y'), ('shift', 'tab'),
}


@dataclass(frozen=True)
class Action:
    type: str
    x: int = 0
    y: int = 0
    button: str = 'left'
    text: str = ''
    key: str = ''
    keys: tuple = ()
    amount: int = 0

    def describe(self):
        if self.type in ('move', 'click'):
            return f'{self.type} en ({self.x}, {self.y}) / 1000, botón {self.button}'
        if self.type == 'scroll':
            return f'Desplazar rueda {self.amount}'
        if self.type == 'type_text':
            return f'Escribir: {self.text!r}'
        if self.type == 'press_key':
            return f'Pulsar: {self.key}'
        if self.type == 'hotkey':
            return f'Atajo: {"+".join(self.keys)}'
        return self.type


def parse_action(obj):
    if not isinstance(obj, dict):
        raise ValueError('La propuesta no es un objeto')
    kind = obj.get('type')
    if kind not in VALID_TYPES:
        raise ValueError(f'Acción no admitida: {kind!r}')
    if kind in ('move', 'click'):
        for coord in ('x', 'y'):
            if type(obj.get(coord)) is not int or not 0 <= obj[coord] <= 1000:
                raise ValueError(f'{coord} debe ser entero de 0 a 1000')
        button = obj.get('button', 'left')
        if button not in ('left', 'right'):
            raise ValueError('Botón no admitido')
        return Action(kind, x=obj['x'], y=obj['y'], button=button)
    if kind == 'scroll':
        amount = obj.get('amount')
        if type(amount) is not int or not -5 <= amount <= 5 or amount == 0:
            raise ValueError('Desplazamiento fuera de límites')
        return Action(kind, amount=amount)
    if kind == 'type_text':
        txt = obj.get('text')
        if not isinstance(txt, str) or not txt or len(txt) > 240:
            raise ValueError('Texto vacío o demasiado largo (máximo 240 caracteres)')
        return Action(kind, text=txt)
    if kind == 'press_key':
        key = obj.get('key')
        if key not in SAFE_KEYS:
            raise ValueError('Tecla no permitida')
        return Action(kind, key=key)
    keys = obj.get('keys')
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError('Atajo incorrecto')
    keys_tuple = tuple(k.lower() for k in keys)
    if keys_tuple not in SAFE_HOTKEYS:
        raise ValueError('Atajo no permitido')
    return Action(kind, keys=keys_tuple)
