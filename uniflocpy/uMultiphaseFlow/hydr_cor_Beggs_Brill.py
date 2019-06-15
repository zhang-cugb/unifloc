
"""
Олег Кобзарь
01.06.2019
oleg.kobzarius@gmail.com
Гидравлическая корреляция Беггз и Брилл в исполнении через класс
"""

import math
import unittest
import uniflocpy.uMultiphaseFlow.friction_Bratland as fr  # модуль для расчета коэффициента трения
import uniflocpy.uTools.uconst as uc

const_g_m2sec = uc.g

# TODO добавить учет расчета сверху вниз


def __calc_hltetta__(data):
    """
    Для расчета объемного содержания жидкости
    :param data: набор всех данных
    :return: ничего, последний расчет - объемное соодержание жидкости с поправкой на угол и поправкой Пэйна
    """
    if data.flow_regime == 0:
        # Segregated Flow - Расслоенный
        a = 0.98
        b = 0.4846
        c = 0.0868
    if data.flow_regime == 1:
        # Intermittent Flow - Прерывистый
        a = 0.845
        b = 0.5351
        c = 0.0173
    if data.flow_regime == 2:
        # Distributed Flow - Распределенный
        a = 1.065
        b = 0.5824
        c = 0.0609
    data.volume_liquid_content_with_zero_angle = a * data.liquid_content ** b / data.val_number_Fr ** c

    data.Nlv = (data.vsl_msec * (data.rho_liquid_kgm3 / (const_g_m2sec * data.sigma_kgsec2)) ** (1 / 4))

    if data.flow_regime == 2:
        data.correction_factor_c = 0
    else:
        if data.flow_regime == 0:
            d = 0.011
            e = -3.768
            f = 3.539
            g = - 1.614
        if data.flow_regime == 1:
            d = 2.96
            e = 0.305
            f = -0.4473
            g = 0.0978

        result = ((1 - data.liquid_content) *
                  math.log(d * data.liquid_content ** e * data.Nlv ** f * data.val_number_Fr ** g))
        if result <= 0:
            data.correction_factor_c = 0
        else:
            data.correction_factor_c = result

    data.angle_correction_factor = (1 + data.correction_factor_c *
                                    ((math.sin(1.8 * data.angle_rad)) - (1/3) *
                                    (math.sin(1.8 * data.angle_rad))**3))

    data.volume_liquid_content_with_angle = data.volume_liquid_content_with_zero_angle * data.angle_correction_factor

    if data.angle_grad > 0:
        data.volume_liquid_content_with_Pains_cor = 0.924 * data.volume_liquid_content_with_angle
    else:
        data.volume_liquid_content_with_Pains_cor = 0.685 * data.volume_liquid_content_with_angle


class Beggs_Brill_cor():
    """
    Класс для хранения данных и расчета градиента давления по методу Беггз и Брилл
    """
    def __init__(self):
        self.mu_oil_pasec = 0.97 * 10 ** (-3)
        self.mu_gas_pasec = 0.016 * 10 ** (-3)
        self.mu_water_pasec = 1 * 10 ** (-3)
        self.mu_liquid_pas = None

        self.sigma_kgsec2 = 8.41 * 10 ** (-3)
        self.watercut_percent = 0

        self.epsilon_friction_m = 18.288 * 10 ** (-6)
        self.diametr_inner_m = 0.152

        self.oil_rate_on_surface_m3day = 1590
        self.gas_rate_on_surface_m3day = 283 * 10 ** 3
        self.water_rate_on_surface_m3day = 0

        self.Rp_m3m3 = 178  # газовый фактор
        self.rs_m3m3 = 50.6
        self.rsw_m3m3 = 0
        self.rho_oil_kgm3 = 762.64
        self.rho_water_kgm3 = 1000
        self.rho_liquid_kgm3 = 762.64
        self.rho_gas_kgm3 = 94.19
        self.bo_m3m3 = 1.197
        self.bw_m3m3 = 1
        self.bg_m3m3 = 0.0091

        self.angle_grad = 90  # угол наклона ствола скважины от горизонтали
        self.angle_rad = self.angle_grad * math.pi / 180
        self.Ap = None  # поперечная площадь трубы

        self.volume_oil_rate_in_PT_m3sec = 0  # объемный дебит нефти при данных условиях (P,T)
        self.volume_water_rate_in_PT_m3sec = 0  # объемный дебит воды при данных условиях (P,T)
        self.volume_liquid_rate_in_PT_m3sec = 0  # объемный дебит жидкости при данных условиях (P,T)
        self.volume_gas_rate_in_PT_m3sec = 0  # объемный дебит газа при данных условиях (P,T)

        self.pressure_pa = 117.13 * 10 ** 5
        self.pressure_bar = self.pressure_pa / 10 ** 6
        self.temperature_c = 82

        self.correction_factor_betta = None
        self.angle_correction_factor = None
        self.volume_liquid_content_with_angle = None

        self.vsl_msec = 0  # приведенная скорость жидкости (3.10)
        self.vsg_msec = 0  # приведенная скорость газа (3.11)
        self.vm_msec = 0  # приведенная (общая) скорость смеси (3.12)

        self.liquid_content = None  # объемное содержание жидкости при отсутствии проскальзывания (3.8)

        self.val_number_Fr = None

        self.flow_regime = None
        self.mu_mix_noslip_pas = None
        self.rhon_kgm3 = None
        self.number_Re = None
        self.friction_coefficient = None
        self.y = None
        self.s = None
        self.result_friction = None
        self.Ek = None
        self.rhos_kgm3 = None
        self.volume_liquid_content_with_Pains_cor = None
        self.result_grad_pam = None
        self.print_all = True

        # импорт модуля для расчета коэффициента трения
        self.module_friction = fr.Friction(self.number_Re, self.epsilon_friction_m, self.diametr_inner_m)

        self.friction_grad_pam = None
        self.density_grad_pam = None
        self.friction_grad_part_percent = None
        self.density_grad_part_percent = None

    def calc_grad(self, PT):
        """
        Функция расчета градиента с использованием исходных данных
        :param PT: начальные условия в виде экземляра класса PT
        :return: градиент давления, Па / м
        """
        self.pressure_pa = PT.p_pa
        self.temperature_c = PT.T_C
        if self.pressure_pa <= 0:
            self.result_grad_pam = 0
            return 0
        else:

            self.Ap = math.pi * self.diametr_inner_m ** 2 / 4  # площадь поперечного сечения трубы, м2

            self.volume_oil_rate_in_PT_m3sec = self.oil_rate_on_surface_m3day * self.bo_m3m3 / 86400  # (3.1)

            self.volume_water_rate_in_PT_m3sec = self.water_rate_on_surface_m3day * self.bw_m3m3 / 86400

            self.volume_liquid_rate_in_PT_m3sec = self.volume_oil_rate_in_PT_m3sec + self.volume_water_rate_in_PT_m3sec

            self.vsl_msec = self.volume_liquid_rate_in_PT_m3sec / self.Ap  # приведенная скорость жидкости (3.10)

            self.volume_gas_rate_in_PT_m3sec = (self.gas_rate_on_surface_m3day -
                                                self.oil_rate_on_surface_m3day * self.rs_m3m3 -
                                                self.water_rate_on_surface_m3day * self.rsw_m3m3) * self.bg_m3m3 / 86400  # (3.3)

            self.vsg_msec = self.volume_gas_rate_in_PT_m3sec / self.Ap  # приведенная скорость газа (3.11)

            self.vm_msec = self.vsl_msec + self.vsg_msec  # приведенная скорость смеси

            self.liquid_content = self.volume_liquid_rate_in_PT_m3sec / (
                    self.volume_liquid_rate_in_PT_m3sec + self.volume_gas_rate_in_PT_m3sec)  # содержание жидкости в потоке

            self.val_number_Fr = self.vm_msec ** 2 / const_g_m2sec / self.diametr_inner_m  # (4.109)

            number_Fr = self.val_number_Fr

            CL = self.liquid_content
            L1 = 316 * CL ** 0.302
            L2 = 0.0009252 * CL ** (-2.4684)
            L3 = 0.1 * CL ** (-1.4516)
            L4 = 0.5 * CL ** (-6.738)
            if (CL < 0.01 and number_Fr < L1) or (CL >= 0.01 and number_Fr < L2):
                # Segregated Flow - разделенный режим
                self.flow_regime = 0
            if (0.01 <= CL < 0.4 and L3 < number_Fr <= L1) or (CL >= 0.4 and L3 < number_Fr <= L4):
                # Intermittent Flow - прерывистый режим
                self.flow_regime = 1
            if (CL < 0.4 and number_Fr >= L1) or (CL >= 0.4 and number_Fr > L4):
                # Distributed Flow - распределенный режим
                self.flow_regime = 2
            if L2 <= number_Fr < L3 and CL >= 0.01:
                # Transition Flow - переходный режим
                self.flow_regime = 3

            if self.flow_regime != 3:
                __calc_hltetta__(self)
            else:
                self.flow_regime = 0
                __calc_hltetta__(self)
                hltetta_segr = self.volume_liquid_content_with_Pains_cor
                self.flow_regime = 1
                __calc_hltetta__(self)
                hltetta_inter = self.volume_liquid_content_with_Pains_cor
                A = (L3 - self.val_number_Fr) / (L3 - L2)
                B = 1 - A
                self.volume_liquid_content_with_Pains_cor = (A * hltetta_segr + B * hltetta_inter)

            self.mu_liquid_pas = (self.mu_water_pasec * self.watercut_percent / 100 +
                                      self.mu_oil_pasec * (1 - self.watercut_percent / 100))

            self.mu_mix_noslip_pas = (self.mu_liquid_pas * self.liquid_content +
                                      self.mu_gas_pasec * (1 - self.liquid_content))

            self.rho_liquid_kgm3 = (self.rho_water_kgm3 * self.watercut_percent / 100 +
                                      self.rho_oil_kgm3 * (1 - self.watercut_percent / 100))

            self.rhon_kgm3 = self.rho_liquid_kgm3 * self.liquid_content + self.rho_gas_kgm3 * (1 - self.liquid_content)

            self.number_Re = self.rhon_kgm3 * self.vm_msec * self.diametr_inner_m / self.mu_mix_noslip_pas

            self.friction_coefficient = self.module_friction.calc_f(self.number_Re, self.epsilon_friction_m,
                                                                 self.diametr_inner_m)

            self.y = self.liquid_content / self.volume_liquid_content_with_Pains_cor ** 2
            if 1 < self.y < 1.2:
                self.s = math.log(2.2 * self.y - 1.2)
            elif 1 == self.y:
                self.s = 0
            else:
                lny = math.log(self.y)
                self.s = lny / (-0.0523 + 3.182 * lny - 0.8725 * lny ** 2 + 0.01853 * lny ** 4)

            self.result_friction = self.friction_coefficient * math.exp(self.s)

            self.Ek = self.vm_msec * self.vsg_msec * self.rhon_kgm3 / self.pressure_pa

            self.rhos_kgm3 = (self.rho_liquid_kgm3 * self.volume_liquid_content_with_Pains_cor +
                             self.rho_gas_kgm3 * (1 - self.volume_liquid_content_with_Pains_cor))

            self.result_grad_pam = ((self.result_friction * self.rhon_kgm3 * self.vm_msec ** 2 / 2 / self.diametr_inner_m +
                                     self.rhos_kgm3 * const_g_m2sec * math.sin(self.angle_rad)) / ( 1 - self.Ek))

            self.friction_grad_pam = (self.result_friction * self.rhon_kgm3 * self.vm_msec ** 2 / 2 / self.diametr_inner_m)

            self.density_grad_pam = self.rhos_kgm3 * const_g_m2sec * math.sin(self.angle_rad)

            self.friction_grad_part_percent = self.friction_grad_pam / (1 - self.Ek) / self.result_grad_pam * 100

            self.density_grad_part_percent = self.density_grad_pam / (1 - self.Ek) / self.result_grad_pam * 100

            return self.result_grad_pam


class PT():
    def __init__(self, p_mpa, t_c):
        self.p_mpa = p_mpa
        self.T_C = t_c
        self.p_pa = self.p_mpa * 10 ** 6
