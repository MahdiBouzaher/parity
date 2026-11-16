data provisions;
  set loans;
  rate = round(pd * lgd, 0.0001);
  prov = exposure * rate;
run;

proc means data=provisions sum;
  var prov;
run;
