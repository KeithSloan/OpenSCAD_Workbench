// Cube expressed as a polyhedron with quad faces

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
        [0, 1, 2, 3],   // bottom
        [4, 5, 6, 7],   // top
        [0, 1, 5, 4],
        [1, 2, 6, 5],
        [2, 3, 7, 6],
        [3, 0, 4, 7]
    ],
    convexity = 10
);

