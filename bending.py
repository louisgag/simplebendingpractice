import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import math
import numpy as np
import scipy.integrate
import sympy


class Beam:
    def __init__(self, length, fixed_and_rolling_support_coords, plot_resolution=1000):
        self.length = length
        self.fixed_coord, self.rolling_coord = fixed_and_rolling_support_coords
        self.load_inventory = []
        self.fixed_load, self.rolling_load = ([0, 0], 0)
        self.plot_resolution = plot_resolution
        self.x_axis = np.linspace(0, self.length, self.plot_resolution)
        empty_vector = np.zeros(shape=(1, self.plot_resolution))
        self.distributed_loads = np.vstack((self.x_axis, empty_vector, empty_vector))
        self.shear_force = np.vstack((self.x_axis, empty_vector))
        self.normal_force = np.vstack((self.x_axis, empty_vector))
        self.bending_moment = np.vstack((self.x_axis, empty_vector))

    def add_load(self, new_load):
        self.load_inventory.append(new_load)
        self.update_reaction_forces()
        if type(new_load).__name__ == "DistributedLoad":
            self.update_distributed_loads()
        self.update_shear_force()
        self.update_normal_force()
        self.update_bending_moment()

    def update_reaction_forces(self):
        d1, d2 = self.fixed_coord, self.rolling_coord
        sum_loads_x = sum(load.resultant.x for load in self.load_inventory)
        sum_loads_y = sum(load.resultant.y for load in self.load_inventory)
        sum_moments = sum(load.moment for load in self.load_inventory)
        a_matrix = np.array([[-1, 0, 0],
                            [0, -1, -1],
                            [0, -d1, -d2]])
        b = np.array([sum_loads_x, sum_loads_y, sum_moments])
        x = np.linalg.inv(a_matrix).dot(b)
        self.fixed_load[0], self.fixed_load[1], self.rolling_load = x

    def update_distributed_loads(self):
        new_distributed_loads = np.zeros(shape=(2, self.plot_resolution))
        for load in self.load_inventory:
            if type(load).__name__ == "DistributedLoad":
                new_distributed_loads += load.value_at(self.distributed_loads[0])
        self.distributed_loads[1:3, :] = new_distributed_loads

    def update_shear_force(self):
        x, fx, fy = self.distributed_loads
        new_shear_force = np.concatenate(([0], scipy.integrate.cumtrapz(fy, x)))

        for idx, coord in enumerate(self.x_axis):
            if self.fixed_coord <= coord:
                new_shear_force[idx] += self.fixed_load[1]
            if self.rolling_coord <= coord:
                new_shear_force[idx] += self.rolling_load

        for load in self.load_inventory:
            if type(load).__name__ == "PointLoad":
                for idx, coord in enumerate(self.x_axis):
                    if load.x_coord <= coord:
                        new_shear_force[idx] += load.resultant.y

        self.shear_force[1] = new_shear_force

    def update_normal_force(self):
        x, fx, fy = self.distributed_loads
        new_normal_force = np.concatenate(([0], scipy.integrate.cumtrapz(-fx, x)))

        for idx, coord in enumerate(self.x_axis):
            if self.fixed_coord <= coord:
                new_normal_force[idx] -= self.fixed_load[0]

        for load in self.load_inventory:
            if type(load).__name__ == "PointLoad":
                for idx, coord in enumerate(self.x_axis):
                    if load.x_coord <= coord:
                        new_normal_force[idx] -= load.resultant.x

        self.normal_force[1] = new_normal_force

    def update_bending_moment(self):
        x, y = self.shear_force
        new_bending_moment = np.concatenate(([0], scipy.integrate.cumtrapz(y, x)))
        for load in self.load_inventory:
            if type(load).__name__ == "PointTorque":
                for idx, coord in enumerate(self.x_axis):
                    if load.x_coord <= coord:
                        new_bending_moment[idx] -= load.moment
        self.bending_moment[1] = new_bending_moment

    def plot_case_this_is_exploratory_coding(self):
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, sharex=True, sharey=False)
        ax1.text(self.length/2, # x coordinate, 0 leftmost positioned, 1 rightmost
         0.5, # y coordinate, 0 topmost positioned, 1 bottommost
         "To do: Sketch with reaction forces", # the text which will be printed
         horizontalalignment='center', # shortcut 'ha'
         verticalalignment='center', # shortcut 'va'
         fontsize=20, # can be named 'font' as well
         alpha=.5 # float (0.0 transparent through 1.0 opaque)
         )
        plot_numerical(ax2, self.normal_force, "Normal force diagram")
        plot_numerical(ax3, self.shear_force, "Shear force diagram")
        plot_numerical(ax4, self.bending_moment, "Bending moment diagram")
        plt.show()


def plot_numerical(ax, xy_array, title):
    ax.plot(xy_array[0], xy_array[1], 'r', linewidth=2)
    a, b = xy_array[0, 0], xy_array[0, -1]
    verts = [(a, 0)] + list(zip(xy_array[0], xy_array[1])) + [(b, 0)]
    poly = Polygon(verts, facecolor='0.9', edgecolor='0.5')
    ax.add_patch(poly)
    ax.set_title(title)
    return plt


class DistributedLoad:
    def __init__(self, coeffs, start_end):
        self.x_left, self.x_right = start_end
        x = sympy.symbols('x')
        x_expr = sum(n * ((x-self.x_left) ** p) for p, n in enumerate(coeffs[0][::-1]))
        y_expr = sum(n * ((x-self.x_left) ** p) for p, n in enumerate(coeffs[1][::-1]))
        self.x_load = sympy.Piecewise((0, x < self.x_left), (0, x > self.x_right), (x_expr, True))
        self.y_load = sympy.Piecewise((0, x < self.x_left), (0, x > self.x_right), (y_expr, True))
        x_force = sympy.integrate(self.x_load, (x, *start_end))
        y_force = sympy.integrate(self.y_load, (x, *start_end))
        x_coord_resultant = sympy.integrate(self.y_load * (x-self.x_left), (x, *start_end)) / y_force + self.x_left
        self.resultant = PointLoad([x_force, y_force], x_coord_resultant)
        self.moment = self.resultant.moment
        self.y_load_old = sum(n * (x ** p) for p, n in enumerate(coeffs[1][::-1]))

    def value_at(self, x_range):
        x = sympy.symbols('x')
        values = np.zeros((2, len(x_range)))
        lam_x_load = sympy.lambdify(x, self.x_load, modules=['numpy'])
        lam_y_load = sympy.lambdify(x, self.y_load, modules=['numpy'])
        values[0, :] = lam_x_load(x_range)
        # TODO: Find out why line 145 breaks one of the tests, fix it and use it to replace lines 143-144
        for idx, coord in enumerate(x_range):
            values[1, idx] = lam_y_load(coord)
        # values[1, :] = lam_y_load(x_range)
        return values


class PointLoad:
    """
    Point load 2D vector applied at a point (counterclockwise positive). 
    Consists of a size 2 iterable and an application point 'x_coord'.
    """
    def __init__(self, vector2d, x_coord):
        self.vector2d = np.array([*vector2d])
        self.x_coord = x_coord
        self.x, self.y = self.vector2d
        self.norm = math.sqrt(sum(comp ** 2 for comp in vector2d))
        self.resultant = self
        self.moment = self.y * x_coord


class PointTorque:
    """
    Torque applied at a point (counterclockwise positive). Consists of a 
    scalar magnitude and an application point 'x_coord'.
    """
    def __init__(self, torque, x_coord):
        self.x_coord = x_coord
        self.resultant = PointLoad([0, 0], x_coord)
        self.moment = torque
