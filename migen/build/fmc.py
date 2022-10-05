from migen.build.generic_platform import *


def _fmc_pin(fmc: str, bank: str, i: int, pol: str):
    bank = bank.upper()
    pol = pol.upper()
    cc_pin_name_tmp = "fmc{fmc}:{bank}{i:02d}_CC_{pol}"
    pin_name_tmp = "fmc{fmc}:{bank}{i:02d}_{pol}"
    cc_pins = {
        "LA": [0, 1, 17, 18],
        "HA": [0, 1, 17],
        "HB": [0, 6, 17],
    }
    if i in cc_pins[bank]:
        return cc_pin_name_tmp.format(fmc=fmc, bank=bank, i=i, pol=pol)
    else:
        return pin_name_tmp.format(fmc=fmc, bank=bank, i=i, pol=pol)


class FMCPlatform:
    def __init__(self, **kwargs):
        self.fmc_config = kwargs

    def _get_bank_io_standard(self, connector, bank):
        if bank in ["LA", "HA"]:
            return self.fmc_config[f"{connector}_vadj"]
        elif bank == "HB":
            return self.fmc_config[f"{connector}_vio_b_m2c"]
        else:
            assert False, f"Invalid bank ({bank})!"

    @staticmethod
    def _what_bank(identifier):
        banks = ["LA", "HA", "HB"]
        for b in banks:
            if b in identifier:
                return b
        assert False, f"Invalid FMC bank ({identifier})!"

    @staticmethod
    def _what_connector(identifier):
        assert ":" in identifier, \
               f"Invalid connector identifier ({identifier})!"
        assert identifier.startswith("fmc"), \
               f"Invalid connector identifier ({identifier})!"
        return identifier.split(":")[0]

    @classmethod
    def _get_entry_bank(cls, entry):
        banks = []
        for s in entry:
            if isinstance(s, Pins):
                for identifier in s.identifiers:
                    banks.append(cls._what_bank(identifier))
            elif isinstance(s, Subsignal):
                banks.append(cls._get_entry_bank(s.constraints))
        assert banks.count(banks[0]) == len(banks), f"Multiple banks per"\
            f" entry not supported ({entry[0]})!"
        return banks[0]

    @classmethod
    def _get_entry_connector(cls, entry):
        connectors = []
        for s in entry:
            if isinstance(s, Pins):
                for identifier in s.identifiers:
                    connectors.append(cls._what_connector(identifier))
            elif isinstance(s, Subsignal):
                connectors.append(cls._get_entry_connector(s.constraints))
        assert connectors.count(connectors[0]) == len(connectors), \
               f"Multiple connectors per entry not supported ({entry[0]})!"
        return connectors[0]

    def add_extension(self, io):
        for entry in io:
            bank = self._get_entry_bank(entry)
            connector = self._get_entry_connector(entry)
            iostd = self._get_bank_io_standard(connector, bank)
            for s in entry: 
                if isinstance(s, IOStandard):
                    if s.name == "diff":
                        s.name = iostd["diff"]
                    elif s.name == "single":
                        s.name = iostd["single"]
                    else:
                        pass
                    assert s.name is not None, \
                       f"Unsupported configuration for entry {entry[0]}!"
        return super().add_extension(io)