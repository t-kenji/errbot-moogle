# -*- coding: utf-8 -*-

import math
import functools
import logging

from errbot import BotPlugin, botcmd
from pytz  import timezone
from datetime import datetime, timedelta
from crontab import CronTab as CrontabProcessor
from random import random


log = logging.getLogger('errbot.plugins.crontab')

class JobManager(object):

    def __init__(self, crontab, tzinfo):
        """
        :param crontab: crontab.CronTab
        """
        self._crontab = crontab
        self._tzinfo = tzinfo

    @property
    def now(self):
        """
        Now datetime
        :return: datetime
        """
        tzinfo = self._tzinfo
        return datetime.now(tzinfo)

    @property
    def next(self):
        """
        Next scheduled
        :return: datetime
        """
        crontab = self._crontab
        tzinfo = self._tzinfo
        return datetime.now(tzinfo) + timedelta(seconds=math.ceil(crontab.next()))

    @property
    def interval(self):
        """
        Time to the next schedule
        :return: seconds
        """
        crontab = self._crontab
        return math.ceil(crontab.next())

class Crontab(BotPlugin):

    def __init__(self, bot):
        super().__init__(bot)

        self._tzinfo = timezone('Asia/Tokyo')
        self._jobs = [
            {
                'crontab': JobManager(CrontabProcessor('* * * * *'), self._tzinfo),
                'callback': self.lottery_of_facilitator,
            },
        ]

    def lottery_of_facilitator(self, *args, **kwargs):
        crontab = [ c.get('crontab') for c in self._jobs if c.get('callback') == self.lottery_of_facilitator ]
        if crontab:
            crontab = crontab[0]

            user = self.build_identifier('@ktakahashi#test')

            candidates = [
                    'user1', 'user2', 'user3',
            ]
            facilitator = candidates[math.floor(len(candidates) * random())]

            self.send(user, 'Todays facilitator is @{} :tada:'.format(facilitator))

            self.stop_poller(self.lottery_of_facilitator, args)
            self.start_poller(crontab.interval, self.lottery_of_facilitator, (crontab.next,))

    def activate(self):
        super().activate()
        self.log.info('Crontab.activate')

        for job in self._jobs:
            crontab = job.get('crontab')
            callback = job.get('callback')
            self.start_poller(crontab.interval, callback, (crontab.next,))

    @botcmd  # flags a command
    def tryme(self, msg, args):  # a command callable with !tryme
        return 'It *works* !'  # This string format is markdown.
