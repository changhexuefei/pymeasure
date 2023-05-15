#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2023 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import re
import time
import numpy as np

from pymeasure.adapters import FakeAdapter
from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_discrete_set


class FakeInstrument(Instrument):
    """ Provides a fake implementation of the Instrument class
    for testing purposes.
    """

    def __init__(self, adapter=None, name="Fake Instrument", includeSCPI=False, **kwargs):
        super().__init__(
            FakeAdapter(**kwargs),
            name,
            includeSCPI=includeSCPI,
            **kwargs
        )

    @staticmethod
    def control(get_command, set_command, docs,
                validator=lambda v, vs: v, values=(), map_values=False,
                get_process=lambda v: v, set_process=lambda v: v,
                check_set_errors=False, check_get_errors=False,
                **kwargs):
        """Fake Instrument.control.

        Strip commands and only store and return values indicated by
        format strings to mimic many simple commands.
        This is analogous how the tests in test_instrument are handled.
        """

        # Regex search to find first format specifier in the command
        fmt_spec_pattern = r'(%[\w.#-+ *]*[diouxXeEfFgGcrsa%])'
        match = re.findall(fmt_spec_pattern, set_command)
        if match:
            # format_specifier = match.group(0)
            format_specifier = ','.join(match)
        else:
            format_specifier = ''
        # To preserve as much functionality as possible, call the real
        # control method with modified get_command and set_command.
        return Instrument.control(get_command="",
                                  set_command=format_specifier,
                                  docs=docs,
                                  validator=validator,
                                  values=values,
                                  map_values=map_values,
                                  get_process=get_process,
                                  set_process=set_process,
                                  check_set_errors=check_set_errors,
                                  check_get_errors=check_get_errors,
                                  **kwargs)


class SwissArmyFake(FakeInstrument):
    """Dummy instrument class useful for testing.

    Like a Swiss Army knife, this class provides multi-tool functionality in the form of streams
    of multiple types of fake data. Data streams that can currently be generated by this class
    include 'voltages', sinusoidal 'waveforms', and mono channel 'image data'.
    """

    def __init__(self, name="Mock instrument", wait=.1, **kwargs):
        super().__init__(
            name=name,
            includeSCPI=False,
            **kwargs
        )
        self._wait = wait
        self._tstart = 0
        self._voltage = 10
        self._output_voltage = 0
        self._time = 0
        self._wave = self.wave
        self._units = {'voltage': 'V',
                       'output_voltage': 'V',
                       'time': 's',
                       'wave': 'a.u.'}
        # mock image attributes
        self._w = 1920
        self._h = 1080
        self._frame_format = "mono_8"

    @property
    def time(self):
        """Control the elapsed time."""
        if self._tstart == 0:
            self._tstart = time.time()
        self._time = time.time() - self._tstart
        return self._time

    @time.setter
    def time(self, value):
        if value == 0:
            self._tstart = 0
        else:
            while self.time < value:
                time.sleep(0.001)

    @property
    def wave(self):
        """Measure a waveform."""
        return float(np.sin(self.time))

    @property
    def voltage(self):
        """Measure the voltage."""
        time.sleep(self._wait)
        return self._voltage

    @property
    def output_voltage(self):
        """Control the voltage."""
        return self._output_voltage

    @output_voltage.setter
    def output_voltage(self, value):
        time.sleep(self._wait)
        self._output_voltage = value

    @property
    def frame_width(self):
        """Control frame width in pixels."""
        time.sleep(self._wait)
        return self._w

    @frame_width.setter
    def frame_width(self, w):
        time.sleep(self._wait)
        self._w = w

    @property
    def frame_height(self):
        """Control frame height in pixels."""
        time.sleep(self._wait)
        return self._h

    @frame_height.setter
    def frame_height(self, h):
        time.sleep(self._wait)
        self._h = h

    @property
    def frame_format(self):
        """Control the format for image data returned from the get_frame() method.
        Allowed values are:
            mono_8: single channel 8-bit image.
            mono_16: single channel 16-bit image.
        """
        time.sleep(self._wait)
        return self._frame_format

    @frame_format.setter
    def frame_format(self, form):
        allowed_formats = ["mono_8", "mono_16"]
        strict_discrete_set(form, allowed_formats)
        self._frame_format = form

    @property
    def frame(self):
        """Get a new image frame."""
        im_format_maxval_dict = {"8": 255, "16": 65535}
        im_format_type_dict = {"8": np.uint8, "16": np.uint16}
        bit_depth = self.frame_format.split("_")[1]
        time.sleep(self._wait)
        return np.array(
            im_format_maxval_dict[bit_depth] * np.random.rand(self.frame_height, self.frame_width),
            dtype=im_format_type_dict[bit_depth]
        )
