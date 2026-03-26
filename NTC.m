syms Vdd R60 R64 R59 R63 RNTC Ua;

U0 = Vdd * R63 / (R59+R63);
Ue = Vdd * R64 / (R64+RNTC);
V = 1+(R60/((R59*R63)/(R59+R63)));

RNTC_sol = solve(Ua == (Ue-U0) * V + U0, RNTC);
char(RNTC_sol)

Vdd = 4.5;
R60 = 1500;
R64 = 5100;
R59 = 10000;
R63 = 10000;
Ua = 4.30497;

double(subs(RNTC_sol))
