// Same cube, but with intentionally mixed winding
// OpenSCAD accepts this, OCC does not unless you fix orientation

polyhedron(
    points = [
        [0, 0, 0],
        [10, 0, 0],
        [10, 10, 0],
        [0, 10, 0],
        [0, 0, 10],
        [10, 0, 10],
        [10, 10, 10],
        [0, 10, 10]
    ],
    faces = [
        [0, 3, 2, 1],   // reversed
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [1, 2, 6, 5],
        [2, 3, 7, 6],
        [3, 0, 4, 7]
    ]
);

