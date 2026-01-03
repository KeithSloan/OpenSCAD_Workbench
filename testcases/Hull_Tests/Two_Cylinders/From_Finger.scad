hull() {
									multmatrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, -1], [0, 0, 0, 1]]) {
										cylinder($fn = 96, $fa = 12, $fs = 2, h = 2, r1 = 9.25, r2 = 9.25, center = true);
									}
									multmatrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, -22], [0, 0, 0, 1]]) {
										cylinder($fn = 96, $fa = 12, $fs = 2, h = 36, r1 = 11.9, r2 = 10, center = true);
									}
                                }