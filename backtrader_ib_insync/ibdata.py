#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015-2020 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import time

import backtrader as bt
from backtrader.feed import DataBase
from backtrader import TimeFrame, date2num, num2date
from backtrader.utils.py3 import integer_types, queue, string_types, with_metaclass
from backtrader.metabase import MetaParams

from .ibstore import IBStore


class MetaIBData(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        """Class has already been created ... register"""
        # Initialize the class
        super(MetaIBData, cls).__init__(name, bases, dct)

        # Register with the store
        IBStore.DataCls = cls


class IBData(with_metaclass(MetaIBData, DataBase)):
    """Interactive Brokers Data Feed.

    Supports the following contract specifications in parameter ``dataname``:

          - TICKER  # Stock type and SMART exchange
          - TICKER-STK  # Stock and SMART exchange
          - TICKER-STK-EXCHANGE  # Stock
          - TICKER-STK-EXCHANGE-CURRENCY  # Stock

          - TICKER-CFD  # CFD and SMART exchange
          - TICKER-CFD-EXCHANGE  # CFD
          - TICKER-CDF-EXCHANGE-CURRENCY  # Stock

          - TICKER-IND-EXCHANGE  # Index
          - TICKER-IND-EXCHANGE-CURRENCY  # Index

          - TICKER-YYYYMM-EXCHANGE  # Future
          - TICKER-YYYYMM-EXCHANGE-CURRENCY  # Future
          - TICKER-YYYYMM-EXCHANGE-CURRENCY-MULT  # Future
          - TICKER-FUT-EXCHANGE-CURRENCY-YYYYMM-MULT # Future

          - TICKER-YYYYMM-EXCHANGE-CURRENCY-STRIKE-RIGHT  # FOP
          - TICKER-YYYYMM-EXCHANGE-CURRENCY-STRIKE-RIGHT-MULT  # FOP
          - TICKER-FOP-EXCHANGE-CURRENCY-YYYYMM-STRIKE-RIGHT # FOP
          - TICKER-FOP-EXCHANGE-CURRENCY-YYYYMM-STRIKE-RIGHT-MULT # FOP

          - CUR1.CUR2-CASH-IDEALPRO  # Forex

          - TICKER-YYYYMMDD-EXCHANGE-CURRENCY-STRIKE-RIGHT  # OPT
          - TICKER-YYYYMMDD-EXCHANGE-CURRENCY-STRIKE-RIGHT-MULT  # OPT
          - TICKER-OPT-EXCHANGE-CURRENCY-YYYYMMDD-STRIKE-RIGHT # OPT
          - TICKER-OPT-EXCHANGE-CURRENCY-YYYYMMDD-STRIKE-RIGHT-MULT # OPT

    Params:

      - ``sectype`` (default: ``STK``)

        Default value to apply as *security type* if not provided in the
        ``dataname`` specification

      - ``exchange`` (default: ``SMART``)

        Default value to apply as *exchange* if not provided in the
        ``dataname`` specification

      - ``currency`` (default: ``''``)

        Default value to apply as *currency* if not provided in the
        ``dataname`` specification

      - ``historical`` (default: ``False``)

        If set to ``True`` the data feed will stop after doing the first
        download of data.

        The standard data feed parameters ``fromdate`` and ``todate`` will be
        used as reference.

        The data feed will make multiple requests if the requested duration is
        larger than the one allowed by IB given the timeframe/compression
        chosen for the data.

      - ``what`` (default: ``None``)

        If ``None`` the default for different assets types will be used for
        historical data requests:

          - 'BID' for CASH assets
          - 'TRADES' for any other

        Use 'ASK' for the Ask quote of cash assets

        Check the IB API docs if another value is wished

      - ``rtbar`` (default: ``False``)

        If ``True`` the ``5 Seconds Realtime bars`` provided by Interactive
        Brokers will be used as the smalles tick. According to the
        documentation they correspond to real-time values (once collated and
        curated by IB)

        If ``False`` then the ``RTVolume`` prices will be used, which are based
        on receiving ticks. In the case of ``CASH`` assets (like for example
        EUR.JPY) ``RTVolume`` will always be used and from it the ``bid`` price
        (industry de-facto standard with IB according to the literature
        scattered over the Internet)

        Even if set to ``True``, if the data is resampled/kept to a
        timeframe/compression below Seconds/5, no real time bars will be used,
        because IB doesn't serve them below that level

      - ``qcheck`` (default: ``0.5``)

        Time in seconds to wake up if no data is received to give a chance to
        resample/replay packets properly and pass notifications up the chain

      - ``backfill_start`` (default: ``True``)

        Perform backfilling at the start. The maximum possible historical data
        will be fetched in a single request.

      - ``backfill`` (default: ``True``)

        Perform backfilling after a disconnection/reconnection cycle. The gap
        duration will be used to download the smallest possible amount of data

      - ``backfill_from`` (default: ``None``)

        An additional data source can be passed to do an initial layer of
        backfilling. Once the data source is depleted and if requested,
        backfilling from IB will take place. This is ideally meant to backfill
        from already stored sources like a file on disk, but not limited to.

      - ``latethrough`` (default: ``False``)

        If the data source is resampled/replayed, some ticks may come in too
        late for the already delivered resampled/replayed bar. If this is
        ``True`` those ticks will bet let through in any case.

        Check the Resampler documentation to see who to take those ticks into
        account.

        This can happen especially if ``timeoffset`` is set to ``False``  in
        the ``IBStore`` instance and the TWS server time is not in sync with
        that of the local computer

      - ``tradename`` (default: ``None``)
        Useful for some specific cases like ``CFD`` in which prices are offered
        by one asset and trading happens in a different onel

        - SPY-STK-SMART-USD -> SP500 ETF (will be specified as ``dataname``)

        - SPY-CFD-SMART-USD -> which is the corresponding CFD which offers not
          price tracking but in this case will be the trading asset (specified
          as ``tradename``)

    The default values in the params are the to allow things like ```TICKER``,
    to which the parameter ``sectype`` (default: ``STK``) and ``exchange``
    (default: ``SMART``) are applied.

    Some assets like ``AAPL`` need full specification including ``currency``
    (default: '') whereas others like ``TWTR`` can be simply passed as it is.

      - ``AAPL-STK-SMART-USD`` would be the full specification for dataname

        Or else: ``IBData`` as ``IBData(dataname='AAPL', currency='USD')``
        which uses the default values (``STK`` and ``SMART``) and overrides
        the currency to be ``USD``
    """

    params = (
        ("sectype", "STK"),  # usual industry value
        ("exchange", "SMART"),  # usual industry value
        ("currency", ""),
        ("rtbar", False),  # use RealTime 5 seconds bars
        ("historical", False),  # only historical download
        ("what", None),  # historical - what to show
        ("useRTH", False),  # historical - download only Regular Trading Hours
        ("qcheck", 0.5),  # timeout in seconds (float) to check for events
        ("backfill_start", True),  # do backfilling at the start
        ("backfill", True),  # do backfilling when reconnecting
        ("backfill_from", None),  # additional data source to do backfill from
        ("latethrough", False),  # let late samples through
        ("tradename", None),  # use a different asset as order target
        ("hist_tzo", 0),  # timezone offset for historical information
    )

    _store = IBStore

    # Minimum size supported by real-time bars
    RTBAR_MINSIZE = (TimeFrame.Seconds, 5)

    # States for the Finite State Machine in _load
    _ST_FROM, _ST_START, _ST_LIVE, _ST_HISTORBACK, _ST_OVER = range(5)

    def _gettz(self):
        # If no object has been provided by the user and a timezone can be
        # found via contractdtails, then try to get it from pytz, which may or
        # may not be available.

        # The timezone specifications returned by TWS seem to be abbreviations
        # understood by pytz, but the full list which TWS may return is not
        # documented and one of the abbreviations may fail
        tzstr = isinstance(self.p.tz, string_types)
        if self.p.tz is not None and not tzstr:
            return bt.utils.date.Localizer(self.p.tz)

        if self.contractdetails is None:
            return None  # nothing can be done

        try:
            import pytz  # keep the import very local
        except ImportError:
            return None  # nothing can be done

        tzs = self.p.tz if tzstr else self.contractdetails.timeZoneId

        if tzs == "CST":  # reported by TWS, not compatible with pytz. patch it
            tzs = "CST6CDT"

        try:
            tz = pytz.timezone(tzs)
        except pytz.UnknownTimeZoneError:
            return None  # nothing can be done

        # contractdetails there, import ok, timezone found, return it
        return tz

    def islive(self):
        """Returns ``True`` to notify ``Cerebro`` that preloading and runonce
        should be deactivated"""
        return not self.p.historical

    def __init__(self, **kwargs):
        self.tradecontractdetails = None
        self.tradecontract = None
        self.contractdetails = None
        self._state = None
        self.contract = None
        self._usertvol = None
        self.qlive = None
        self.qhist = None
        self.ibstore = self._store(**kwargs)
        self.precontract = self.parsecontract(self.p.dataname)
        self.pretradecontract = self.parsecontract(self.p.tradename)

    def setenvironment(self, env):
        """Receives an environment (cerebro) and passes it over to the store it
        belongs to"""
        super(IBData, self).setenvironment(env)
        env.addstore(self.ibstore)

    def parsecontract(self, dataname):
        """Parses dataname generates a default contract"""
        # Set defaults for optional tokens in the ticker string
        if dataname is None:
            return None

        exch = self.p.exchange
        curr = self.p.currency
        expiry = ""
        strike = 0.0
        right = ""
        mult = ""

        # split the ticker string
        tokens = iter(dataname.split("-"))

        # Symbol and security type are compulsory
        symbol = next(tokens)
        try:
            sectype = next(tokens)
        except StopIteration:
            sectype = self.p.sectype

        # security type can be an expiration date
        if sectype.isdigit():
            expiry = sectype  # save the expiration ate

            if len(sectype) == 6:  # YYYYMM
                sectype = "FUT"
            else:  # Assume OPTIONS - YYYYMMDD
                sectype = "OPT"

        if sectype == "CASH":  # need to address currency for Forex
            symbol, curr = symbol.split(".")

        # See if the optional tokens were provided
        try:
            exch = next(tokens)  # on exception it will be the default
            curr = next(tokens)  # on exception it will be the default

            if sectype == "FUT":
                if not expiry:
                    expiry = next(tokens)
                mult = next(tokens)

                # Try to see if this is FOP - Futures on OPTIONS
                right = next(tokens)
                # if still here this is a FOP and not a FUT
                sectype = "FOP"
                strike, mult = float(mult), ""  # assign to strike and void

                mult = next(tokens)  # try again to see if there is any

            elif sectype == "OPT":
                if not expiry:
                    expiry = next(tokens)
                strike = float(next(tokens))  # on exception - default
                right = next(tokens)  # on exception it will be the default

                mult = next(tokens)  # ?? no harm in any case

        except StopIteration:
            pass

        # Make the initial contract
        precon = self.ibstore.make_contract(
            symbol=symbol,
            sectype=sectype,
            exch=exch,
            curr=curr,
            expiry=expiry,
            strike=strike,
            right=right,
            mult=mult,
        )

        return precon

    def start(self):
        """Starts the IB connection and gets the real contract and
        contractdetails if it exists"""
        super(IBData, self).start()
        # Kickstart store and get queue to wait on
        self.qlive = self.ibstore.start(data=self)

        self._usertvol = not self.p.rtbar
        tfcomp = (self._timeframe, self._compression)
        if tfcomp < self.RTBAR_MINSIZE:
            # Requested timeframe/compression not supported by rtbars
            self._usertvol = True

        self.contract = None
        self.contractdetails = None
        self.tradecontract = None
        self.tradecontractdetails = None

        if self.p.backfill_from is not None:
            self._state = self._ST_FROM
            self.p.backfill_from.setenvironment(self._env)
            self.p.backfill_from._start()
        else:
            self._state = self._ST_START  # initial state for _load
        # self._statelivereconn = False  # if reconnecting in live state
        # self._subcription_valid = False  # subscription state
        # self._storedmsg = dict()  # keep pending live message (under None)

        self.put_notification(self.CONNECTED)
        # get real contract details with real conId (contractId)
        cds = self.ibstore.get_contract_details(self.precontract, maxcount=1)
        if cds is not None:
            cdetails = cds[0]
            # self.contract = cdetails.contractDetails.summary
            # self.contractdetails = cdetails.contractDetails
            self.contract = cdetails.contract
            self.contractdetails = cdetails
        else:
            # no contract can be found (or many)
            self.put_notification(self.DISCONNECTED)
            return

        if self.pretradecontract is None:
            # no different trading asset - default to standard asset
            self.tradecontract = self.contract
            self.tradecontractdetails = self.contractdetails

        else:
            # different target asset (typical of some CDS products)
            # use other set of details
            cds = self.ibstore.get_contract_details(self.pretradecontract, maxcount=1)
            if cds is not None:
                cdetails = cds[0]
                self.tradecontract = cdetails.contract
                self.tradecontractdetails = cdetails
            else:
                # no contract can be found (or many)
                self.put_notification(self.DISCONNECTED)
                return

        if self._state == self._ST_START:
            self._start_finish()  # to finish initialization
            self._st_start()

    def stop(self):
        """Stops and tells the store to stop"""
        super(IBData, self).stop()
        self.ibstore.stop()

    def haslivedata(self):
        return bool(self.qlive)

    def _load(self):
        if self.contract is None or self._state == self._ST_OVER:
            return False  # nothing can be done

        # print("# state={}, size={}".format(self._state, len(self.lines.datetime)))

        while True:
            if self._state == self._ST_LIVE:
                if self._usertvol:
                    self.qlive = self.ibstore.req_mkt_data(
                        self.contract, what=self.p.what
                    )
                else:
                    self.qlive = self.ibstore.req_real_time_bars(
                        self.contract, what=self.p.what
                    )

                if not self.qlive.empty():
                    msg = self.qlive.get()

                    if self._usertvol:
                        ret = self._load_rtvolume(msg)
                    else:
                        ret = self._load_rtbar(
                            msg, hist=False, hist_tzo=self.p.hist_tzo
                        )
                    if ret:
                        return True
            elif self._state == self._ST_HISTORBACK:
                if not self.qhist.empty():
                    msg = self.qhist.get()  # timeout=self.p.qcheck)
                    ret = self._load_rtbar(msg, hist=True, hist_tzo=self.p.hist_tzo)
                    if ret:
                        return True
                # not historical only, continute live data.
                elif not self.p.historical:
                    self.put_notification(self.LIVE)
                    self._state = self._ST_LIVE
                    continue
                # historical only
                else:
                    self.put_notification(self.DISCONNECTED)
                    return False
            elif self._state == self._ST_FROM:
                if not self.p.backfill_from.next():
                    # additional data source is consumed
                    self._state = self._ST_START
                    continue

                # copy lines of the same name
                for alias in self.lines.getlinealiases():
                    lsrc = getattr(self.p.backfill_from.lines, alias)
                    ldst = getattr(self.lines, alias)

                    print("{}[0]={}".format(alias, lsrc[0]))
                    ldst[0] = lsrc[0]

                return True

            elif self._state == self._ST_START:
                if not self._st_start():
                    return False

    def _st_start(self):
        if self.p.historical:
            self.put_notification(self.DELAYED)
            dtend = None
            if self.todate < float("inf"):
                dtend = num2date(self.todate)

            dtbegin = None
            if self.fromdate > float("-inf"):
                dtbegin = num2date(self.fromdate)

            self.qhist = self.ibstore.req_historical_data_ex(
                contract=self.contract,
                enddate=dtend,
                begindate=dtbegin,
                timeframe=self._timeframe,
                compression=self._compression,
                what=self.p.what,
                useRTH=self.p.useRTH,
                tz=self._tz,
                sessionend=self.p.sessionend,
            )

            self._state = self._ST_HISTORBACK
            return True  # continue before
        elif self.p.backfill_start:
            self.put_notification(self.DELAYED)

            dtline = self.lines.datetime
            dtbegin = num2date(dtline[-1]) if len(dtline) > 1 else None
            print("st_start:dtbegin={}".format(dtbegin))
            dtend = None
            self.qhist = self.ibstore.req_historical_data_ex(
                contract=self.contract,
                enddate=dtend,
                begindate=dtbegin,
                timeframe=self._timeframe,
                compression=self._compression,
                what=self.p.what,
                useRTH=self.p.useRTH,
                tz=self._tz,
                sessionend=self.p.sessionend,
            )

            self._state = self._ST_HISTORBACK
            return True

        self._state = self._ST_LIVE
        return True  # no return before - implicit continue

    def _load_rtbar(self, rtbar, hist=False, hist_tzo=None):
        # A complete 5 second bar made of real-time ticks is delivered and
        # contains open/high/low/close/volume prices
        # The historical data has the same data but with 'date' instead of
        # 'time' for datetime
        if hist:
            if hist_tzo is None:
                hist_tzo = time.timezone / 3600
                rtbar.date = rtbar.date + datetime.timedelta(hours=hist_tzo)
            dt = date2num(rtbar.date)
        else:
            dt = date2num(rtbar.time)
        if dt < self.lines.datetime[-1] and not self.p.latethrough:
            return False  # cannot deliver earlier than already delivered

        self.lines.datetime[0] = dt
        # Put the tick into the bar
        try:
            self.lines.open[0] = rtbar.open
        except AttributeError:
            self.lines.open[0] = rtbar.open_
        self.lines.high[0] = rtbar.high
        self.lines.low[0] = rtbar.low
        self.lines.close[0] = rtbar.close
        self.lines.volume[0] = rtbar.volume
        self.lines.openinterest[0] = 0

        print(
            "rtbar:d={}, h={}, l={}, c={}, o={}, v={}".format(
                num2date(dt),
                rtbar.high,
                rtbar.low,
                rtbar.close,
                self.lines.open[0],
                rtbar.volume,
            )
        )

        return True

    def _load_rtvolume(self, rtvol):
        # A single tick is delivered and is therefore used for the entire set
        # of prices. Ideally the
        # contains open/high/low/close/volume prices
        # Datetime transformation
        dt = date2num(rtvol.time)
        if dt < self.lines.datetime[-1] and not self.p.latethrough:
            return False  # cannot deliver earlier than already delivered

        self.lines.datetime[0] = dt

        # Put the tick into the bar
        tick = rtvol.price
        self.lines.open[0] = tick
        self.lines.high[0] = tick
        self.lines.low[0] = tick
        self.lines.close[0] = tick
        self.lines.volume[0] = rtvol.size
        self.lines.openinterest[0] = 0

        return True
