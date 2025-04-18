#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2025 PyMeasure Developers
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
import time
import os
import json

import numpy as np
import pandas as pd

from pymeasure.instruments import Channel, Instrument, SCPIUnknownMixin
from pymeasure.instruments.validators import (strict_discrete_set,
                                              truncated_discrete_set,
                                              strict_range)

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

######
# MAIN
######


class Agilent4156(SCPIUnknownMixin, Instrument):
    """ Represents the Agilent 4155/4156 Semiconductor Parameter Analyzer
    and provides a high-level interface for taking current-voltage (I-V) measurements.

    .. code-block:: python

        from pymeasure.instruments.agilent import Agilent4156

        # explicitly define r/w terminations; set sufficiently large timeout or None.
        smu = Agilent4156("GPIB0::25", read_termination = '\\n', write_termination = '\\n',
                          timeout=None)

        # reset the instrument
        smu.reset()

        # define configuration file for instrument and load config
        smu.configure("configuration_file.json")

        # save data variables, some or all of which are defined in the json config file.
        smu.save(['VC', 'IC', 'VB', 'IB'])

        # take measurements
        status = smu.measure()

        # measured data is a pandas dataframe and can be exported to csv.
        data = smu.get_data(path='./t1.csv')

    The JSON file is an ascii text configuration file that defines the settings of each channel
    on the instrument. The JSON file is used to configure the instrument using the convenience
    function :meth:`~.Agilent4156.configure` as shown in the example above. For example, the
    instrument setup for a bipolar transistor measurement is shown below.

    .. code-block:: json

         {
                "SMU1": {
                    "voltage_name" : "VC",
                    "current_name" : "IC",
                    "channel_function" : "VAR1",
                    "channel_mode" : "V",
                    "series_resistance" : "0OHM"
                },

                "SMU2": {
                    "voltage_name" : "VB",
                    "current_name" : "IB",
                    "channel_function" : "VAR2",
                    "channel_mode" : "I",
                    "series_resistance" : "0OHM"
                },

                "SMU3": {
                    "voltage_name" : "VE",
                    "current_name" : "IE",
                    "channel_function" : "CONS",
                    "channel_mode" : "V",
                    "constant_value" : 0,
                    "compliance" : 0.1
                },

                 "SMU4": {
                    "voltage_name" : "VS",
                    "current_name" : "IS",
                    "channel_function" : "CONS",
                    "channel_mode" : "V",
                    "constant_value" : 0,
                    "compliance" : 0.1
                },

                "VAR1": {
                    "start" : 1,
                    "stop" : 2,
                    "step" : 0.1,
                    "spacing" : "LINEAR",
                    "compliance" : 0.1
                },

                "VAR2": {
                    "start" : 0,
                    "step" : 10e-6,
                    "points" : 3,
                    "compliance" : 2

                }
            }

    """

    def __init__(self, adapter, name="Agilent 4155/4156 Semiconductor Parameter Analyzer",
                 **kwargs):
        super().__init__(
            adapter,
            name,
            **kwargs
        )

        self.smu1 = SMU(self, 'SMU1')
        self.smu2 = SMU(self, 'SMU2')
        self.smu3 = SMU(self, 'SMU3')
        self.smu4 = SMU(self, 'SMU4')
        self.vmu1 = VMU(self, 'VMU1')
        self.vmu2 = VMU(self, 'VMU2')
        self.vsu1 = VSU(self, 'VSU1')
        self.vsu2 = VSU(self, 'VSU2')
        self.var1 = VAR1(self)
        self.var2 = VAR2(self)
        self.vard = VARD(self)

    analyzer_mode = Instrument.control(
        ":PAGE:CHAN:MODE?", ":PAGE:CHAN:MODE %s",
        """Control the instrument operating mode.

        - Values: :code:`SWEEP`, :code:`SAMPLING`

        .. code-block:: python

            smu.analyzer_mode = "SWEEP"
        """,
        validator=strict_discrete_set,
        values={'SWEEP': 'SWE', 'SAMPLING': 'SAMP'},
        map_values=True,
        check_set_errors=True,
        check_get_errors=True
    )

    integration_time = Instrument.control(
        ":PAGE:MEAS:MSET:ITIM?", ":PAGE:MEAS:MSET:ITIM %s",
        """Control the integration time.

        - Values: :code:`SHORT`, :code:`MEDIUM`, :code:`LONG`

        .. code-block:: python

            instr.integration_time = "MEDIUM"
        """,
        validator=strict_discrete_set,
        values={'SHORT': 'SHOR', 'MEDIUM': 'MED', 'LONG': 'LONG'},
        map_values=True,
        check_set_errors=True,
        check_get_errors=True
    )

    delay_time = Instrument.control(
        ":PAGE:MEAS:DEL?", ":PAGE:MEAS:DEL %g",
        """Control the measurement delay time in seconds,
        which can take the values from 0 to 65s in 0.1s steps.

        .. code-block:: python

            instr.delay_time = 1 # delay time of 1-sec
        """,
        validator=truncated_discrete_set,
        values=np.arange(0, 65.1, 0.1),
        check_set_errors=True,
        check_get_errors=True
    )

    hold_time = Instrument.control(
        ":PAGE:MEAS:HTIME?", ":PAGE:MEAS:HTIME %g",
        """Control the measurement hold time in seconds,
        which can take the values from 0 to 655s in 1s steps.

        .. code-block:: python

            instr.hold_time = 2 # hold time of 2-secs.
        """,
        validator=truncated_discrete_set,
        values=np.arange(0, 655, 1),
        check_set_errors=True,
        check_get_errors=True
    )

    def stop(self):
        """Stop the ongoing measurement.

        .. code-block:: python

            instr.stop()
        """
        self.write(":PAGE:SCON:STOP")

    def measure(self, period="INF", points=100):
        """
        Perform a single measurement and wait for completion in sweep mode.

        In sampling mode, the measurement period and number of points can be specified.

        :param period: Period of sampling measurement from 6E-6 to 1E11 seconds.
            Default setting is :code:`INF`.
        :param points: Number of samples to be measured, from 1 to 10001.
            Default setting is :code:`100`.

        .. code-block::python

            instr.measure() #for sweep measurement
            instr.measure(period=100, points=100) #for sampling measurement
        """
        if self.analyzer_mode == "SWEEP":
            self.write(":PAGE:SCON:MEAS:SING; *OPC?")

        else:
            self.write(f":PAGE:MEAS:SAMP:PER {period}")
            self.write(f":PAGE:MEAS:SAMP:POIN {points}")
            self.write(":PAGE:SCON:MEAS:SING; *OPC?")

    def disable_all(self):
        """ Disable all channels in the instrument.

        .. code-block:: python

            instr.disable_all()
        """
        self.smu1.reset_settings()
        time.sleep(0.1)
        self.smu2.reset_settings()
        time.sleep(0.1)
        self.smu3.reset_settings()
        time.sleep(0.1)
        self.smu4.reset_settings()
        time.sleep(0.1)
        self.vmu1.reset_settings()
        time.sleep(0.1)
        self.vmu2.reset_settings()
        time.sleep(0.1)

    def configure(self, config_file):
        """ Configure the channel setup and sweep using a JSON configuration file.

        (JSON is the `JavaScript Object Notation`_)

        .. _`JavaScript Object Notation`: https://www.json.org/

        :param config_file: JSON file to configure instrument channels.

        .. code-block:: python

            instr.configure('config.json')
        """
        self.disable_all()
        obj_dict = {'SMU1': self.smu1,
                    'SMU2': self.smu2,
                    'SMU3': self.smu3,
                    'SMU4': self.smu4,
                    'VMU1': self.vmu1,
                    'VMU2': self.vmu2,
                    'VSU1': self.vsu1,
                    'VSU2': self.vsu2,
                    'VAR1': self.var1,
                    'VAR2': self.var2,
                    'VARD': self.vard
                    }
        with open(config_file) as stream:
            try:
                instr_settings = json.load(stream)
            except json.JSONDecodeError as e:
                print(e)

        # replace dict keys with Instrument objects
        new_settings_dict = {}
        for key, value in instr_settings.items():
            new_settings_dict[obj_dict[key]] = value

        for obj, setup in new_settings_dict.items():
            for setting, value in setup.items():
                setattr(obj, setting, value)
                time.sleep(0.1)

    def save(self, trace_list):
        """ Save the voltage or current in the instrument display list

        :param trace_list: A list of channel variables whose measured data should be saved.
            A maximum of 8 variables are allowed. If only one variable is being saved, a string
            can be specified.

        .. code-block:: python

            instr.save(['IC', 'IB', 'VC', 'VB']) #for list of variables
            instr.save('IC')    #for single variable
        """
        self.write(":PAGE:DISP:MODE LIST")
        if isinstance(trace_list, list):
            if len(trace_list) > 8:
                raise RuntimeError('Maximum of 8 variables allowed')
            else:
                for name in trace_list:
                    self.write(f":PAGE:DISP:LIST \'{name}\'")
        elif isinstance(trace_list, str):
            self.write(f":PAGE:DISP:LIST \'{trace_list}\'")
        else:
            raise TypeError(
                'Must be a string if only one variable is saved, or else a list if'
                'multiple variables are being saved.'
            )

    def save_var(self, trace_list):
        """ Save the voltage or current in the instrument variable list.

        This is useful if one or two more variables need to be saved in addition to the 8
        variables allowed by :meth:`~.Agilent4156.save`.

        :param trace_list: A list of channel variables whose measured   data should be saved.
            A maximum of 2 variables are allowed. If only one variable is being saved, a string
            can be specified.

        .. code-block:: python

            instr.save_var(['VA', 'VB'])
        """
        self.write(":PAGE:DISP:MODE LIST")
        if isinstance(trace_list, list):
            if len(trace_list) > 2:
                raise RuntimeError('Maximum of 2 variables allowed')
            else:
                for name in trace_list:
                    self.write(f":PAGE:DISP:DVAR \'{name}\'")
        elif isinstance(trace_list, str):
            self.write(f":PAGE:DISP:DVAR \'{trace_list}\'")
        else:
            raise TypeError(
                'Must be a string if only one variable is saved, or else a list if'
                'multiple variables are being saved.'
            )

    @property
    def data_variables(self):
        """
        Get a string list of data variables for which measured data is available.

        This looks for all the variables saved by the :meth:`~.Agilent4156.save` and
        :meth:`~.Agilent4156.save_var` methods and returns it. This is useful for creation
        of dataframe headers.

        :returns: List

        .. code-block:: python

            header = instr.data_variables
        """
        dlist = self.ask(":PAGE:DISP:LIST?").split(',')
        dvar = self.ask(":PAGE:DISP:DVAR?").split(',')
        varlist = dlist + dvar
        return list(filter(None, varlist))

    def get_data(self, path=None):
        """
        Get the measurement data from the instrument after completion.

        If the measurement period is set to :code:`INF` in the :meth:`~.Agilent4156.measure`
        method, then the measurement must be stopped using :meth:`~.Agilent4156.stop` before
        getting valid data.

        :param path: Path for optional data export to CSV.
        :returns: Pandas Dataframe

        .. code-block:: python

            df = instr.get_data(path='./datafolder/data1.csv')
        """
        if int(self.ask('*OPC?')):
            header = self.data_variables
        self.write(":FORM:DATA ASC")
        # recursively get data for each variable
        for i, listvar in enumerate(header):
            data = self.values(f":DATA? \'{listvar}\'")
            time.sleep(0.01)
            if i == 0:
                lastdata = data
            else:
                data = np.column_stack((lastdata, data))
                lastdata = data

        df = pd.DataFrame(data=data, columns=header, index=None)
        if path is not None:
            _, ext = os.path.splitext(path)
            if ext != ".csv":
                path = path + ".csv"
            df.to_csv(path, index=False)

        return df


def check_current_voltage_name(name):
    if (len(name) > 6) or not name[0].isalpha():
        new_name = 'a' + name[:5]
        log.info(f"Renaming {name} to {new_name}...")
        name = new_name
    return name


##########
# CHANNELS
##########

class AgilentMeasurementChannel(Channel):
    """Offers some common properties."""

    voltage_name = Channel.control(
        "PAGE:CHAN:{ch}:VNAME?",
        ":PAGE:CHAN:{ch}:VNAME \'%s\'",
        """ Control the voltage name of the channel.

        If input is greater than 6 characters long or starts with a number,
        the name is autocorrected and prepended with 'a'. Event is logged.

        .. code-block:: python

            instr.smu1.voltage_name = "Vbase"
        """,
        set_process=check_current_voltage_name,
    )

    def reset_settings(self):
        """Reset the settings of this channel to default value.

        .. code-block:: python

            instr.smu1.reset_settings()
        """
        self.write(":PAGE:CHAN:{ch}:DIS")
        return self.check_errors()

    @property
    def disable(self):
        """Set the settings of this channel to default value.

        .. code-block:: python

            instr.smu1.disable
        """
        self.reset_settings()

    channel_mode = Channel.control(
        ":PAGE:CHAN:{ch}:MODE?",
        ":PAGE:CHAN:{ch}:MODE %s",
        """Control the channel mode.""",
        values=[],
        validator=strict_discrete_set,
        check_get_errors=True,
        check_set_errors=True,
        dynamic=True,
    )

    channel_function = Channel.control(
        ":PAGE:CHAN:{ch}:FUNC?",
        ":PAGE:CHAN:{ch}:FUNC %s",
        """Control the channel function.

        - Values: :code:`VAR1`, :code:`VAR2`, :code:`VARD` or :code:`CONS`.
        """,
        check_get_errors=True,
        check_set_errors=True,
        validator=strict_discrete_set,
        values=["VAR1", "VAR2", "VARD", "CONS"],
    )


class SMU(AgilentMeasurementChannel):
    """SMU of Agilent 4155/4156 Semiconductor Parameter Analyzer"""

    def __init__(self, parent, id, **kwargs):
        super().__init__(
            parent,
            id.upper(),
            **kwargs
        )
        self.channel_mode_values = ["V", "I", "COMM"]

    series_resistance = Channel.control(
        ":PAGE:CHAN:{ch}:SRES?",
        ":PAGE:CHAN:{ch}:SRES %s",
        """ Control the series resistance of SMU<n>.

        - Values: :code:`0OHM`, :code:`10KOHM`, :code:`100KOHM`, or :code:`1MOHM`

        .. code-block:: python

            instr.smu1.series_resistance = "10KOHM"

        """,
        check_get_errors=True,
        check_set_errors=True,
        validator=strict_discrete_set,
        values=["0OHM", "10KOHM", "100KOHM", "1MOHM"],
    )

    @property
    def constant_value(self):
        """Control the constant source value of SMU<n>.

        You use this command only if :meth:`~.SMU.channel_function`
        is :code:`CONS` and also :meth:`~.SMU.channel_mode` should not be :code:`COMM`.

        :param const_value: Voltage in (-200V, 200V) and current in (-1A, 1A). Voltage or current
            depends on if :meth:`~.SMU.channel_mode` is set to :code:`V` or :code:`I`.

        .. code-block:: python

            instr.smu1.constant_value = 1

        """
        if self.parent.analyzer_mode == "SWEEP":
            value = self.ask(":PAGE:MEAS:CONS:{ch}?")
        else:
            value = self.ask(":PAGE:MEAS:SAMP:CONS:{ch}?")
        self.check_errors()
        return value

    @constant_value.setter
    def constant_value(self, const_value):
        validator = strict_range
        values = self.__validate_cons()
        value = validator(const_value, values)
        if self.parent.analyzer_mode == 'SWEEP':
            self.write(f":PAGE:MEAS:CONS:{{ch}} {value}")
        else:
            self.write(":PAGE:MEAS:SAMP:CONS:{} {}".format(
                self.channel, value))
        self.check_errors()

    @property
    def compliance(self):
        """Control the *constant* compliance value of SMU<n>.

        If the SMU channel is setup as a variable (VAR1, VAR2, VARD) then compliance limits are
        set by the variable definition.

        - Value: Voltage in (-200V, 200V) and current in (-1A, 1A) based
          on :meth:`~.SMU.channel_mode`.

        .. code-block:: python

            instr.smu1.compliance = 0.1
        """
        if self.parent.analyzer_mode == "SWEEP":
            value = self.ask(":PAGE:MEAS:CONS:{ch}:COMP?")
        else:
            value = self.ask(
                ":PAGE:MEAS:SAMP:CONS:{ch}:COMP?")
        self.check_errors()
        return value

    @compliance.setter
    def compliance(self, comp):
        validator = strict_range
        values = self.__validate_compl()
        value = validator(comp, values)
        if self.parent.analyzer_mode == 'SWEEP':
            self.write(":PAGE:MEAS:CONS:{}:COMP {}".format(
                self.channel, value))
        else:
            self.write(":PAGE:MEAS:SAMP:CONS:{}:COMP {}".format(
                self.channel, value))
        self.check_errors()

    current_name = Channel.control(
        "PAGE:CHAN:{ch}:INAME?",
        ":PAGE:CHAN:{ch}:INAME \'%s\'",
        """ Control the current name of the channel.

        If input is greater than 6 characters long or starts with a number,
        the name is autocorrected and prepended with 'a'. Event is logged.

        .. code-block:: python

            instr.smu1.voltage_name = "Vbase"
        """,
        set_process=check_current_voltage_name,
    )

    def __validate_cons(self):
        """Validates the instrument settings for operation in constant mode.
        """
        if not ((self.channel_mode != 'COMM') and (
                self.channel_function == 'CONS')):
            raise ValueError(
                'Cannot set constant SMU function when SMU mode is COMMON, '
                'or when SMU function is not CONSTANT.'
            )
        else:
            values = valid_iv(self.channel_mode)
        return values

    def __validate_compl(self):
        """Validates the instrument compliance for operation in constant mode.
        """
        if not ((self.channel_mode != 'COMM') and (
                self.channel_function == 'CONS')):
            raise ValueError(
                'Cannot set constant SMU parameters when SMU mode is COMMON, '
                'or when SMU function is not CONSTANT.'
            )
        else:
            values = valid_compliance(self.channel_mode)
        return values


class VMU(AgilentMeasurementChannel):
    """VMU of Agilent 4155/4156 Semiconductor Parameter Analyzer"""

    def __init__(self, parent, id, **kwargs):
        super().__init__(
            parent,
            id=id.upper(),
            **kwargs
        )
        self.channel_mode_values = ["V", "DVOL"]


class VSU(AgilentMeasurementChannel):
    """VSU of Agilent 4155/4156 Semiconductor Parameter Analyzer"""

    def __init__(self, parent, id, **kwargs):
        super().__init__(
            parent,
            id.upper(),
            **kwargs
        )

    @property
    def constant_value(self):
        """Control the constant source value of VSU<n>.

        .. code-block:: python

            instr.vsu1.constant_value = 0
        """
        if self.parent.analyzer_mode == "SWEEP":
            value = self.ask(":PAGE:MEAS:CONS:{ch}?")
        else:
            value = self.ask(":PAGE:MEAS:SAMP:CONS:{ch}?")
        self.check_errors()
        return value

    @constant_value.setter
    def constant_value(self, const_value):
        validator = strict_range
        values = [-200, 200]
        value = validator(const_value, values)
        if self.parent.analyzer_mode == 'SWEEP':
            self.write(f":PAGE:MEAS:CONS:{{ch}} {value}")
        else:
            self.write(":PAGE:MEAS:SAMP:CONS:{} {}".format(
                self.channel, value))
        self.check_errors()


#################
# SWEEP VARIABLES
#################


class VARX(Channel):
    """ Base class to define sweep variable settings."""

    def __init__(self, parent, id, **kwargs):
        super().__init__(
            parent,
            id.upper(),
            **kwargs
        )

    @property
    def channel_mode(self):
        """Control the channel mode."""
        channels = ['SMU1', 'SMU2', 'SMU3', 'SMU4', 'VSU1', 'VSU2']
        for ch in channels:
            ch_func = self.ask(f":PAGE:CHAN:{ch}:FUNC?")
            if ch_func == self.id:
                ch_mode = self.ask(f":PAGE:CHAN:{ch}:MODE?")
        return ch_mode

    @property
    def start(self):
        """Control the sweep START value.

        .. code-block:: python

            instr.var1.start = 0
        """
        value = self.ask(":PAGE:MEAS:{ch}:STAR?")
        self.check_errors()
        return value

    @start.setter
    def start(self, value):
        validator = strict_range
        values = valid_iv(self.channel_mode)
        set_value = validator(value, values)
        self.write(f":PAGE:MEAS:{{ch}}:STAR {set_value}")
        self.check_errors()

    @property
    def stop(self):
        """Control the sweep STOP value.

        .. code-block:: python

            instr.var1.stop = 3
        """
        value = self.ask(":PAGE:MEAS:{ch}:STOP?")
        self.check_errors()
        return value

    @stop.setter
    def stop(self, value):
        validator = strict_range
        values = valid_iv(self.channel_mode)
        set_value = validator(value, values)
        self.write(f":PAGE:MEAS:{{ch}}:STOP {set_value}")
        self.check_errors()

    @property
    def step(self):
        """Control the sweep STEP value.

        .. code-block:: python

            instr.var1.step = 0.1
        """
        value = self.ask(":PAGE:MEAS:{ch}:STEP?")
        self.check_errors()
        return value

    @step.setter
    def step(self, value):
        validator = strict_range
        values = 2 * valid_iv(self.channel_mode)
        set_value = validator(value, values)
        self.write(f":PAGE:MEAS:{{ch}}:STEP {set_value}")
        self.check_errors()

    @property
    def compliance(self):
        """Control the sweep COMPLIANCE value.

        .. code-block:: python

            instr.var1.compliance = 0.1
        """
        value = self.ask(":PAGE:MEAS:{}:COMP?")
        self.check_errors()
        return value

    @compliance.setter
    def compliance(self, value):
        validator = strict_range
        values = 2 * valid_compliance(self.channel_mode)
        set_value = validator(value, values)
        self.write(f":PAGE:MEAS:{{ch}}:COMP {set_value}")
        self.check_errors()


class VAR1(VARX):
    """ Class to handle all the specific definitions needed for VAR1.
    Most common methods are inherited from base class.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            "VAR1",
            **kwargs
        )

    spacing = Channel.control(
        ":PAGE:MEAS:{ch}:SPAC?",
        ":PAGE:MEAS:{ch}:SPAC %s",
        """
        Control the sweep type of VAR1.

        - Values: :code:`LINEAR`, :code:`LOG10`, :code:`LOG25`, :code:`LOG50`.
        """,
        validator=strict_discrete_set,
        values={'LINEAR': 'LIN', 'LOG10': 'L10',
                'LOG25': 'L25', 'LOG50': 'L50'},
        map_values=True,
        check_set_errors=True,
        check_get_errors=True
    )


class VAR2(VARX):
    """ Class to handle all the specific definitions needed for VAR2.
    Common methods are imported from base class.
    """

    def __init__(self, adapter, **kwargs):
        super().__init__(
            adapter,
            "VAR2",
            **kwargs
        )

    points = Channel.control(
        ":PAGE:MEAS:{ch}:POINTS?",
        ":PAGE:MEAS:{ch}:POINTS %g",
        """
        Control the number of sweep steps of VAR2.
        You use this command only if there is an SMU or VSU
        whose function (FCTN) is VAR2.

        .. code-block:: python

            instr.var2.points = 10
        """,
        validator=strict_discrete_set,
        values=range(1, 128),
        check_set_errors=True,
        check_get_errors=True
    )


class VARD(Channel):
    """ Class to handle all the definitions needed for VARD.
    VARD is always defined in relation to VAR1.
    """

    def __init__(self, parent, id="VARD", **kwargs):
        super().__init__(
            parent,
            id,
            **kwargs
        )

    @property
    def channel_mode(self):
        """Control the channel mode."""
        channels = ['SMU1', 'SMU2', 'SMU3', 'SMU4', 'VSU1', 'VSU2']
        for ch in channels:
            ch_func = self.ask(f":PAGE:CHAN:{ch}:FUNC?")
            if ch_func == "VARD":
                ch_mode = self.ask(f":PAGE:CHAN:{ch}:MODE?")
        return ch_mode

    @property
    def offset(self):
        """
        Control the OFFSET value of VARD.
        For each step of sweep, the output values of VAR1' are determined by the
        following equation: VARD = VAR1 X RATio + OFFSet
        You use this command only if there is an SMU or VSU whose function is VARD.

        .. code-block:: python

            instr.vard.offset = 1
        """
        value = self.ask(":PAGE:MEAS:VARD:OFFSET?")
        self.check_errors()
        return value

    @offset.setter
    def offset(self, offset_value):
        validator = strict_range
        values = 2 * valid_iv(self.channel_mode)
        value = validator(offset_value, values)
        self.write(f":PAGE:MEAS:VARD:OFFSET {value}")
        self.check_errors()

    ratio = Instrument.control(
        ":PAGE:MEAS:VARD:RATIO?",
        ":PAGE:MEAS:VARD:RATIO %g",
        """
        Control the RATIO of VAR1'.
        For each step of sweep, the output values of VAR1' are determined by the
        following equation: VAR1’ = VAR1 * RATio + OFFSet
        You use this command only if there is an SMU or VSU whose function
        (FCTN) is VAR1'.

        .. code-block:: python

            instr.vard.ratio = 1
        """,
    )

    @property
    def compliance(self):
        """Control the sweep COMPLIANCE value of VARD.

        .. code-block:: python

            instr.vard.compliance = 0.1
        """
        value = self.ask(":PAGE:MEAS:VARD:COMP?")
        self.check_errors()
        return value

    @compliance.setter
    def compliance(self, value):
        validator = strict_range
        values = 2 * valid_compliance(self.channel_mode)
        set_value = validator(value, values)
        self.write(f":PAGE:MEAS:VARD:COMP {set_value}")
        self.check_errors()


def valid_iv(channel_mode):
    if channel_mode == 'V':
        values = [-200, 200]
    elif channel_mode == 'I':
        values = [-1, 1]
    else:
        raise ValueError(
            'Channel is not in V or I mode. It might be disabled.')
    return values


def valid_compliance(channel_mode):
    if channel_mode == 'I':
        values = [-200, 200]
    elif channel_mode == 'V':
        values = [-1, 1]
    else:
        raise ValueError(
            'Channel is not in V or I mode. It might be disabled.')
    return values
