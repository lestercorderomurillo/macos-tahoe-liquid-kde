"""Localized operation summary, driven by backend events rather than console text."""

PHASES = (
    ('system', 'System checks'), ('dependencies', 'Dependencies'),
    ('downloads', 'Downloads'), ('build', 'Building components'),
    ('install', 'Installing components'), ('apply', 'Applying preferences'),
    ('verify', 'Final checks'),
)
COMPONENTS = {
    'kvantum': 'Menu style', 'plasmoids': 'Launcher and Dock',
    'globalmenu': 'Global menu', 'acrylic_glass': 'Acrylic Glass',
    'rounded_corners': 'Rounded Corners', 'clipboard': 'Clipboard',
}


class ProgressModel:
    def __init__(self, action='install'):
        phases = PHASES if action != 'uninstall' else (
            ('system', 'System checks'), ('restore', 'Restoring desktop settings'),
            ('remove', 'Removing components'))
        self.phases = {key: {'label': label, 'state': 'pending'} for key, label in phases}
        self.tasks = {}
        self.warnings = []
        self.active = None
        self.terminal = False

    def accept(self, event):
        if self.terminal or not isinstance(event, dict):
            return
        kind = event.get('kind')
        if kind == 'warning':
            message = event.get('message')
            if isinstance(message, str) and message not in self.warnings:
                self.warnings.append(message[:2000])
            return
        state = event.get('state')
        if state not in ('pending', 'running', 'done', 'failed', 'skipped', 'unchanged'):
            return
        key = event.get('id')
        if not isinstance(key, str):
            return
        if kind == 'phase' and key in self.phases:
            self.phases[key]['state'] = state
            if state == 'running':
                self.active = key
        elif kind == 'build' and key in COMPONENTS:
            self.tasks[key] = {'label': COMPONENTS[key], 'state': state}

    @property
    def preparation_fraction(self):
        preparing = ("system", "dependencies", "downloads", "build")
        finished = {"done", "unchanged", "skipped"}
        completed = sum(self.phases[key]["state"] in finished for key in preparing)
        if self.phases["build"]["state"] == "running" and self.tasks:
            completed += sum(task["state"] in finished for task in self.tasks.values()) / len(self.tasks)
        return completed / len(preparing)

    @property
    def application_started(self):
        return self.active in ("install", "apply", "verify") and "install" in self.phases

    def finish(self, code):
        if self.terminal:
            return
        self.terminal = True
        for row in (*self.phases.values(), *self.tasks.values()):
            if row['state'] == 'running':
                row['state'] = 'cancelled' if code == 130 else 'failed' if code else 'done'
        # A phase never announced by the backend is not evidence of completion.

    def text(self, translate=str):
        marks = {'pending': '·', 'running': '●', 'done': '✓', 'failed': '✗',
                 'cancelled': '–', 'skipped': '–', 'unchanged': '✓'}
        lines = []
        for key, row in self.phases.items():
            suffix = ' · ' + translate('Skipped') if row['state'] == 'skipped' else ' · ' + translate('Unchanged') if row['state'] == 'unchanged' else ''
            lines.append(marks[row['state']] + '  ' + translate(row['label']) + suffix)
            if key == 'build':
                for task in self.tasks.values():
                    lines.append('    ' + marks[task['state']] + '  ' + translate(task['label']))
        if self.warnings:
            lines.extend(['', translate('Warnings'), *('  ' + message for message in self.warnings)])
        return '\n'.join(lines)

    def failed_label(self):
        return next((row['label'] for row in self.tasks.values() if row['state'] == 'failed'),
                    self.phases.get(self.active, {}).get('label', 'installation'))


def elapsed_text(seconds, translate=str):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    template = "{minutes} min {seconds:02d} sec" if minutes else "{seconds} sec"
    return translate(template).format(minutes=minutes, seconds=seconds)
