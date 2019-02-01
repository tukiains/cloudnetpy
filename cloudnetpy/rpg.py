"""This module contains RPG Cloud Radar related functions."""
import os
from collections import namedtuple
import numpy as np
import numpy.ma as ma


class Rpg:
    """RPG Cloud Radar Level 1 data reader."""
    def __init__(self, filename):
        self.filename = filename
        self._file_position = 0
        self._dual_pol = False
        self.header = self.read_rpg_header()
        self.data = self.read_rpg_data()

    @staticmethod
    def read_string(file_id):
        """Read characters from binary data until whitespace."""
        str_out = ''
        while True:
            c = np.fromfile(file_id, np.int8, 1)
            if c:
                str_out += chr(c)
            else:
                break
        return str_out

    def read_rpg_header(self):
        """Reads the header or rpg binary file."""

        def append(names, dtype=np.int32, n_values=1):
            """Updates header dictionary."""
            for name in names:
                header[name] = np.fromfile(file, dtype, int(n_values))

        header = {}
        file = open(self.filename, 'rb')
        append(('file_code', 'header_length'))
        append(('start_time', 'stop_time'), np.uint32)
        append(('program_number', ))
        append(('model_number', ))  # 0 = single pol, 1 = dual pol., 2 = dual pol. in LDR config. ????
        header['program_name'] = Rpg.read_string(file)
        header['customer_name'] = Rpg.read_string(file)
        append(('frequency', 'antenna_separation', 'antenna_diameter',
                'antenna_gain', 'half_power_beam_width'), np.float32)
        append(('dual_polarization',), np.int8)  # 0 = single pol, 1 = dual pol (LDR), 2 = dual pol (STSR)   ????
        append(('sample_duration', ), np.float32)
        append(('latitude', 'longitude'), np.float32)
        append(('calibration_interval_in_samples', ))
        append(('n_range_gates', 'n_temperature_levels', 'n_humidity_levels',
                'n_chirp_sequences'))
        append(('range',), np.float32, header['n_range_gates'])
        append(('temperature_levels',), np.float32, header['n_temperature_levels'])
        append(('humidity_levels',), np.float32, header['n_humidity_levels'])
        append(('n_spectral_samples_in_chirp', 'chirp_start_indices',
                'n_averaged_chirps'), n_values=header['n_chirp_sequences'])
        append(('integration_time', 'range_resolution', 'max_velocity'),
               np.float32, header['n_chirp_sequences'])
        append(('is_power_levelling', 'is_spike_filter', 'is_phase_correction',
                'is_relative_power_correction'), np.int8)
        append(('FFT_window', ), np.int8)  # 0 = square, 1 = parzen, 2 = blackman, 3 = welch, = slepian2, 5 = slepian3
        append(('input_voltage_mV',))
        append(('noise_filter_threshold_factor',), np.float32)
        self._file_position = file.tell()
        file.close()
        if header['dual_polarization'] > 0:
            self._dual_pol = True
        header['antenna_gain'] = 10 * np.log10(header['antenna_gain'])
        return header

    def read_rpg_data(self):
        """Reads the actual data from rpg binary file."""
        Dimensions = namedtuple('Dimensions', ['n_samples',
                                               'n_gates',
                                               'n_layers_t',
                                               'n_layers_h'])

        def create_dimensions():
            """Returns loop lengths for the data read."""
            n_samples = np.fromfile(file, np.int32, 1)
            return Dimensions(int(n_samples),
                              int(self.header['n_range_gates']),
                              int(self.header['n_temperature_levels']),
                              int(self.header['n_humidity_levels']))

        def create_shapes():
            """Returns possible shapes of the data arrays."""
            return((dims.n_samples,),
                   (dims.n_samples, dims.n_layers_t),
                   (dims.n_samples, dims.n_layers_h),
                   (dims.n_samples, dims.n_gates))

        def create_variables():
            """Variable names, data arrays and input data types.

            These need to be defined in the same order as they appear in
            the file.

            """
            shapes = create_shapes()
            fun = np.zeros
            vrs = {}
            # Variable group 0
            vrs['sample_length'] = (fun(shapes[0], np.int), np.int32)  # in Bytes without 'sample_length' itself
            vrs['time'] = (fun(shapes[0], np.int), np.uint32)
            vrs['time_ms'] = (fun(shapes[0], np.int), np.int32)
            # Quality flag: bit 2 = ADC saturation, bit 3 = spectral width too high, bit 4 = no transm. power leveling
            vrs['quality_flag'] = (fun(shapes[0], np.int), np.int8)
            # Variable group 1
            for var_name in ('rain_rate', 'relative_humidity', 'temperature',
                             'pressure', 'wind_speed', 'wind_direction',
                             'voltage', 'brightness_temperature',
                             'liquid_water_path', 'IF_power', 'elevation',
                             'azimuth', 'status_flags', 'transmitted_power',
                             'transmitter_temperature', 'receiver_temperature',
                             'pc_temperature'):
                vrs[var_name] = (fun(shapes[0]), np.float32)
            vrs['temperature_profile'] = (fun(shapes[1]), np.float32)
            for var_name in ('absolute_humidity_profile',
                             'relative_humidity_profile'):
                vrs[var_name] = (fun(shapes[2]), np.float32)
            # Variable group 2
            for var_name in ('sensitivity_limit_of_vertical_polarization',
                             'sensitivity_limit_of_horizontal_polarization'):
                vrs[var_name] = (fun(shapes[3]), np.float32)
            vrs['is_data_in_cell'] = (fun(shapes[3], np.int), np.int8)
            # Variable groups 3 and 4
            for var_name in ('reflectivity', 'velocity', 'width',  # group 3
                             'skewness', 'kurtosis',
                             'ldr', 'spectral_correlation_coeff',  # group 4
                             'differential_phase'):
                vrs[var_name] = (fun(shapes[3]), np.float32)
            return vrs

        def get_keyranges():
            """Returns dict-names for the different 'groups' of variables.

            The variables are grouped in the binary file into 5 groups.
            The keyranges make it easy to separate these groups once
            you know the first and last variable name in each group.

            """
            def _keyrange(key1, key2):
                """List of keys from one key to another."""
                ind1 = keys.index(key1)
                ind2 = keys.index(key2)
                return keys[ind1:ind2 + 1]

            keys = list(data.keys())
            return (_keyrange('sample_length', 'pc_temperature'),
                    _keyrange('absolute_humidity_profile',
                              'relative_humidity_profile'),
                    _keyrange('sensitivity_limit_of_vertical_polarization',
                              'is_data_in_cell'),
                    _keyrange('reflectivity', 'kurtosis'),
                    _keyrange('ldr', 'differential_phase'))

        def append(name, n_elements):
            """Append data into already allocated arrays."""
            array, dtype = data[name]
            values = np.fromfile(file, dtype, n_elements)
            if n_elements == 1 and array.ndim == 1:
                array[sample] = values
            elif n_elements == 1 and array.ndim == 2:
                array[sample][gate] = values
            else:
                array[sample][:] = values

        def _fix_output():
            """Returns just the data arrays as MaskedArrays."""
            out = {}
            for name in data:
                out[name] = ma.masked_equal(data[name][0], 0)
            return out

        file = open(self.filename, 'rb')
        file.seek(self._file_position)
        dims = create_dimensions()
        data = create_variables()
        keyranges = get_keyranges()

        for sample in range(dims.n_samples):

            for key in keyranges[0]:
                append(key, 1)

            _ = np.fromfile(file, np.int32, 3)

            append('temperature_profile', dims.n_layers_t)

            for key in keyranges[1]:
                append(key, dims.n_layers_h)

            for key in keyranges[2]:
                append(key, dims.n_gates)

            for gate in range(dims.n_gates):

                if data['is_data_in_cell'][0][sample][gate]:

                    for key in keyranges[3]:
                        append(key, 1)

                    if self._dual_pol:
                        for key in keyranges[4]:
                            append(key, 1)
        file.close()
        return _fix_output()


def get_rpg_files(path_to_l1_files):
    """Returns list of RPG Level 1 files for one day - sorted by filename."""
    files = os.listdir(path_to_l1_files)
    l1_files = [path_to_l1_files+file for file in files if file.endswith('LV1')]
    l1_files.sort()
    return l1_files


def get_rpg_objects(rpg_files):
    """Creates a list of Rpg() objects from the filenames."""
    for file in rpg_files:
        yield Rpg(file)


def concatenate_rpg_data(rpg_objects):
    """Combines data from hourly Rpg() objects."""
    fields = ('Time', 'Zv', 'LDR', 'CorrC', 'PhiX', 'SW', 'Skew',
              'Kurt', 'Vel', 'LWP', 'T', 'RH', 'TransPow')
    radar = dict.fromkeys(fields, np.array([]))
    for rpg in rpg_objects:
        for name in fields:
            radar[name] = (np.concatenate((radar[name], rpg.data[name]))
                           if radar[name].size else rpg.data[name])
    return radar


def rpg2nc(path_to_l1_files, output_file):
    l1_files = get_rpg_files(path_to_l1_files)
    rpg_objects = get_rpg_objects(l1_files)
    rpg_data = concatenate_rpg_data(rpg_objects)


