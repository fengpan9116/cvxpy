"""
Copyright 2017 Robin Verschueren

This file is part of CVXPY.

CVXPY is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

CVXPY is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with CVXPY.  If not, see <http://www.gnu.org/licenses/>.
"""

import abc
import numpy as np

import cvxpy.settings as s
from cvxpy.reductions import Reduction, Solution, InverseData
from cvxpy.utilities.coeff_extractor import CoeffExtractor
from cvxpy.atoms import reshape
from cvxpy import problems
from cvxpy.problems.objective import Minimize


class MatrixStuffing(Reduction):
    """TODO(akshayka): Document this class."""
    __metaclass__ = abc.ABCMeta

    def apply(self, problem):
        inverse_data = InverseData(problem)

        new_obj, new_var = self.stuffed_objective(problem, inverse_data)
        # Form the constraints
        extractor = CoeffExtractor(inverse_data)
        new_cons = []
        for con in problem.constraints:
            arg_list = []
            for arg in con.args:
                A, b = extractor.get_coeffs(arg)
                arg_list.append(reshape(A*new_var + b, arg.shape))
            new_cons.append(con.copy(arg_list))
            inverse_data.cons_id_map[con.id] = new_cons[-1].id

        # Map of old constraint id to new constraint id.
        inverse_data.minimize = type(problem.objective) == Minimize
        new_prob = problems.problem.Problem(Minimize(new_obj), new_cons)
        return new_prob, inverse_data

    def invert(self, solution, inverse_data):
        """Returns the solution to the original problem given the inverse_data."""
        var_map = inverse_data.var_offsets
        con_map = inverse_data.cons_id_map
        # Flip sign of opt val if maximize.
        opt_val = solution.opt_val
        if solution.status not in s.ERROR and not inverse_data.minimize:
            opt_val = -solution.opt_val

        primal_vars, dual_vars = {}, {}
        if solution.status not in s.SOLUTION_PRESENT:
            return Solution(solution.status, opt_val, primal_vars, dual_vars,
                            solution.attr)

        # Split vectorized variable into components.
        x_opt = solution.primal_vars.values()[0]
        for var_id, offset in var_map.items():
            shape = inverse_data.var_shapes[var_id]
            size = np.prod(shape)
            primal_vars[var_id] = np.reshape(x_opt[offset:offset+size], shape,
                                             order='F')
        # Remap dual variables.
        for old_con, new_con in con_map.items():
            # TODO(akshayka): This line results in key errors often,
            # determine why
            dual_vars[old_con] = solution.dual_vars[new_con]

        # Add constant part
        if inverse_data.minimize:
            opt_val += inverse_data.r
        else:
            opt_val -= inverse_data.r

        return Solution(solution.status, opt_val, primal_vars, dual_vars,
                        solution.attr)

    def stuffed_objective(self, problem, inverse_data):
        return NotImplementedError
