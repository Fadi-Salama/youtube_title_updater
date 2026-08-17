#!/usr/bin/env python3
"""Print every title the schedule can produce. Costs nothing; touches nothing."""

import sys
from datetime import datetime, timedelta

from auto_title_updater import (MAX_TITLE_LENGTH, SERVICE_SCHEDULE, WEEKDAY_NAMES,
                      generate_title, validate_schedule)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, ValueError):
    pass


def main() -> None:
    problems = validate_schedule()
    if problems:
        print('SCHEDULE PROBLEMS')
        for problem in problems:
            print('  !', problem)
        print()

    # Anchor on the most recent Monday so weekday numbers line up.
    monday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    monday -= timedelta(days=monday.weekday())

    print(f'{"Day":<10} {"Window":<15} {"Len":>4}  Title')
    print('-' * 100)

    for weekday, (sh, sm), (eh, em), _ in SERVICE_SCHEDULE:
        when = monday + timedelta(days=weekday, hours=sh, minutes=sm)
        title = generate_title(when)
        flag = '!' if len(title) >= MAX_TITLE_LENGTH else ' '
        print(f'{WEEKDAY_NAMES[weekday]:<10} '
              f'{sh:02d}:{sm:02d}-{eh:02d}:{em:02d}     '
              f'{len(title):>4}{flag} {title}')

    print('-' * 100)
    outside = monday + timedelta(days=2, hours=13)      # Wednesday 13:00
    print(f'{"(default)":<10} {"any other time":<15} '
          f'{len(generate_title(outside)):>4}  {generate_title(outside)}')
    print(f'\nRight now: {generate_title()}')


if __name__ == '__main__':
    main()