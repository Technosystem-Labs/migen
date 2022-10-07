from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform


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
    def __init__(self, fmc_config):
        self.fmc_config = fmc_config
        # TODO: Verify fmc_config
        self.bank_ab_compatible = \
            {  fmc: self._ab_compatible(fmc) for fmc in self.fmc_config.keys() }
        
    def _ab_compatible(self, fmc):
        config = self.fmc_config[fmc]
        
        def compare_standard(std):
            bank_a = config["bank_a"][std]
            bank_b = config["bank_b"][std]
            if bank_a is None or bank_b is None:
                return False
            if len(bank_a) != len(bank_b):
                return False
            bank_a_str = sorted([repr(c) for c in bank_a])
            bank_b_str = sorted([repr(c) for c in bank_b])
            for ca, cb in zip(bank_a_str, bank_b_str): 
                if ca != cb:
                    return False
            return True
        
        return {
            "single": compare_standard("single"),
            "diff": compare_standard("diff")
        }      

    @staticmethod
    def _what_bank(identifier):
        mapping = {"LA": "bank_a", "HA": "bank_a", "HB": "bank_b"}
        for k, v in mapping.items():
            if k in identifier:
                return v
        assert False, f"Invalid FMC bank ({identifier})!"

    @staticmethod
    def _what_connector(identifier):
        assert ":" in identifier, \
               f"Invalid connector identifier ({identifier})!"
        assert identifier.startswith("fmc"), \
               f"Invalid connector identifier ({identifier})!"
        return identifier.split(":")[0]

    @classmethod
    def _get_banks(cls, *constraints):
        banks = []
        for s in constraints:
            if isinstance(s, Pins):
                for identifier in s.identifiers:
                    banks.append(cls._what_bank(identifier))
            elif isinstance(s, Subsignal):
                banks += cls._get_banks(*s.constraints)
        return banks

    @classmethod
    def _get_connector(cls, *constaints):
        connectors = []
        for c in constaints:
            if isinstance(c, Pins):
                for identifier in c.identifiers:
                    connectors.append(cls._what_connector(identifier))
            elif isinstance(c, Subsignal):
                connectors.append(cls._get_connector(*c.constraints))
        if not connectors:
            # Not FMC
            return None
        assert connectors.count(connectors[0]) == len(connectors), \
               f"Multiple connectors per entry not supported!"
        return connectors[0]
    
    def _are_banks_compatible(self, connector, std, *banks):
        if banks.count(banks[0]) == len(banks):
            return True
        else:
            return self.bank_ab_compatible[connector][std]
    
    def _transform_simple(self, *constraints):
        connector = self._get_connector(*constraints)
        banks = self._get_banks(*constraints)
        new_constraints = []
        for c in constraints:
            if isinstance(c, IOStandard):
                if c.name in ["single", "diff"]:
                    assert self._are_banks_compatible(connector, c.name, *banks), \
                           "Incompatible IO standards!"
                    new_constraints += self.fmc_config[connector][banks[0]][c.name]
                else:
                    new_constraints.append(c)
            elif isinstance(c, Subsignal):
                c.constraints = self._transform_simple(*c.constraints)
                new_constraints.append(c)
            else:
                new_constraints.append(c)
        return new_constraints
                                  
    def _transform_constraints(self, *constraints):
        connector = self._get_connector(*constraints)
        if connector is None:
            return constraints
        return self._transform_simple(*constraints)

    def add_extension(self, io):
        new_io = []
        for entry in io:
            try:
                new_io.append([
                    *(entry[:2]),
                    *self._transform_constraints(*(entry[2:]))
                ])
            except AssertionError as e:
                raise AssertionError(f"{e} ({entry[0]})")
        return super().add_extension(new_io)
    
    
if __name__ == "__main__":
    # TODO: Move to unit test
    
    class TestPlatform(FMCPlatform, GenericPlatform):
        def __init__(self):
            _connectors = [
                ("come_conn", {
                    "HA04_N": "M25",
                    "HA04_P": "M24",
                    "HA05_N": "H29",
                    "HA05_P": "J29",
                }),
                ("fmc1", {
                    "HA00_CC_N": "K29",
                    "HA00_CC_P": "K28",
                    "HA02_N": "P22",
                    "HA02_P": "P21",
                    "HB00_CC_N": "F13",
                    "HB00_CC_P": "G13",
                    "HB01_N": "G15",
                    "HB01_P": "H15",
                    "LA00_CC_N": "C27",
                    "LA00_CC_P": "D27",
                    "LA02_N": "G30",
                    "LA02_P": "H30"
                })
            ]
            fmc_config = { 
                "fmc1": {
                    "bank_a": {
                        "single": [IOStandard("BAR"), Misc("FOO")],
                        "diff":   [IOStandard("DIFF_VADJ"), Misc("FOO")]
                    },
                    "bank_b": {
                        "single": [IOStandard("BAR"), Misc("FOO")],
                        "diff":   [IOStandard("BAR"), Misc("FOO")]
                    }
                }
            }
            FMCPlatform.__init__(self, fmc_config)                
            GenericPlatform.__init__(self, "dummy", [], _connectors)

            
    io = lambda fmc: [
        (f"fmc{fmc}_spi", 0,
            Subsignal("sck", Pins(_fmc_pin(fmc, "HA", 0, "p"))),
            Subsignal("miso", Pins(_fmc_pin(fmc, "HB", 0, "p"))),
            IOStandard("single")
        ),
        
    ]        
 
    platform = TestPlatform()
    platform.add_extension(io(fmc=1))
    print(platform.constraint_manager.available)
