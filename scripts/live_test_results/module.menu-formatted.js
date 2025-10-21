const __vite__mapDeps = (i,
  m = __vite__mapDeps,
  d = (m.f || (m.f = ["assets/pcDynamicParameterRecord-D_IQLH_6.js", "assets/index-B1hMJ3MF.js", "assets/index-BYrCvDok.css", "assets/PumpCirculationDay-DHRlPTuX.js", "assets/TariffDay-BdHISs4R.js"]))) => i.map(i => d[i]);
import {
  d as _A,
  c as MA,
  aj as TA,
  u as mA,
  f as EA,
  af as PA,
  h as pA,
  k as OA,
  l as b,
  q as AA,
  n as F,
  w as Y,
  v as J,
  p as U,
  C as g,
  m as sA,
  F as tA,
  B as IA,
  z as H,
  H as oA,
  _ as iA, $ as cA,
  b as SA,
  r as $,
  a0 as j,
  t as LA,
  T as q,
  a7 as CA,
  Y as NA,
  G as UA,
  I as a,
  N as vA,
  D as YA,
  ak as e,
  a9 as A,
  al as E
}
  from "./index-B1hMJ3MF.js";
import {
  c as VA,
  _ as yA,
  t as wA
}
  from "./module.menu.timezones-DZgO-r-J.js";
import {
  ScheduleNames as RA,
  Schedules as WA
}
  from "./AKTUALNA_TARYFA_READ-B3Qa-7om.js";
import "./ParametersViewTypes-C6Grobg3.js";
import "./ThreeWayValveState-CXMvNxVb.js";
const hA = {
  class: "tw-text-3xl tw-text-center tw-text-secondary tw-my-2"
},
  BA = _A({
    __name: "FanViewer",
    props: {
      parameters: {}
    },
    setup(eA) {
      const z = oA(() => iA(() => import("./pcDynamicParameterRecord-D_IQLH_6.js"),
        __vite__mapDeps([0, 1, 2]))), {
          t: O } = MA(), {
            colors: w } = TA.theme.global.current.value, {
              width: f } = mA(),
        K = eA,
        v = EA(() => K.parameters.special.map(({
          parameter: o }) => o)), [V,
            l,
            c,
            y,
            k,
            h,
            i,
            B,
            G,
            t] = v.value,
        C = () => {
          let o = document.getElementById("my-canvas"),
            d = document.getElementsByClassName("chart-type-container")[0].offsetWidth - 50;
          d > 820 && (d = 820);
          const Z = d,
            W = d / 2;
          o.style.width = Z + "px",
            o.style.height = W + "px";
          const L = window.devicePixelRatio;
          o.width = Z * L,
            o.height = W * L;
          const {
            width: R,
            height: r } = o.getBoundingClientRect();
          if (o.getContext) {
            const _ = o.getContext("2d");
            _.scale(L,
              L);
            let T = "14px Arial",
              s = "14px Arial";
            window.innerWidth <= 400 ? (T = "6px Arial",
              s = "6px Arial") : window.innerWidth <= 500 ? (T = "8px Arial",
                s = "8px Arial") : window.innerWidth <= 650 && (T = "10px Arial",
                  s = "10px Arial");
            const p = w.secondary_70,
              I = "white",
              S = "green";
            _.font = T,
              _.fillStyle = I;
            const P = {
              x: R * .25,
              y: r * .35
            },
              m = {
                x: R * .4,
                y: r * .62
              },
              X = {
                x: R * .73,
                y: r * .62
              },
              D = {
                x1: R * .07,
                y1: r * .185,
                x2: R * .07,
                y2: r * .855,
                x3: R * .82,
                y3: r * .85
              },
              N = {
                currentSpeed: {
                  text: {
                    x: R * .55,
                    y: r * .1
                  },
                  value: {
                    x: R * .95,
                    y: r * .1
                  }
                },
                modbusSpeed: {
                  text: {
                    x: R * .55,
                    y: r * .17
                  },
                  value: {
                    x: R * .95,
                    y: r * .17
                  }
                },
                modbusSpeedRPM: {
                  text: {
                    x: R * .55,
                    y: r * .24
                  },
                  value: {
                    x: R * .95,
                    y: r * .25
                  }
                }
              };
            _.beginPath(),
              _.moveTo(D.x1,
                D.y1),
              _.lineTo(D.x2,
                D.y2),
              _.lineTo(D.x3,
                D.y3),
              _.strokeStyle = p,
              _.lineWidth = 1,
              _.stroke(),
              _.closePath(),
              _.beginPath(),
              _.moveTo(D.x1,
                P.y),
              _.lineTo(P.x,
                P.y),
              _.lineTo(m.x,
                m.y),
              _.lineTo(X.x,
                X.y),
              _.strokeStyle = S,
              _.lineWidth = 1,
              _.stroke(),
              _.closePath(),
              _.beginPath(),
              _.setLineDash([5, 4.2]),
              _.moveTo(D.x1,
                m.y),
              _.lineTo(m.x,
                m.y),
              _.strokeStyle = p,
              _.stroke(),
              _.closePath(),
              _.beginPath(),
              _.setLineDash([5, 4.5]),
              _.moveTo(P.x,
                D.y3),
              _.lineTo(P.x,
                P.y),
              _.strokeStyle = p,
              _.stroke(),
              _.closePath(),
              _.beginPath(),
              _.setLineDash([5, 4]),
              _.moveTo(m.x,
                D.y3),
              _.lineTo(m.x,
                m.y),
              _.strokeStyle = p,
              _.stroke(),
              _.closePath();
            const x = new Path2D;
            x.moveTo(P.x,
              P.y),
              x.arc(P.x,
                P.y, 3, 0, 2 * Math.PI),
              _.fillStyle = S,
              _.fill(x),
              x.closePath();
            const Q = new Path2D;
            Q.moveTo(m.x,
              m.y),
              Q.arc(m.x,
                m.y, 3, 0, 2 * Math.PI),
              _.fillStyle = S,
              _.fill(Q),
              Q.closePath(),
              n(_, `${G.value !== null ? G.value + "% max" : "brak max"}`,
                T, "#5b5b5b",
                p,
                D.x1,
                P.y),
              n(_, `${t.value !== null ? t.value + "% min" : "brak min"}`,
                T, "#5b5b5b",
                p,
                D.x1,
                m.y),
              n(_, "min",
                T, "#5b5b5b",
                p,
                P.x,
                D.y3, "0.0"),
              n(_, "max",
                T, "#5b5b5b",
                p,
                m.x,
                D.y3, "13.0"),
              n(_,
                O("canvas.speed"),
                T, "#5b5b5b",
                p,
                R * .03,
                r * .1,
                O("canvas.fan"), "left"),
              n(_,
                O("canvas.temperature"),
                T, "#5b5b5b",
                p,
                D.x3,
                D.y3,
                O("canvas.outdoor"), "center"),
              _.font = s,
              _.fillStyle = w.secondary_70,
              _.textAlign = "left",
              _.fillText(O("canvas.actualSpeed"),
                N.currentSpeed.text.x,
                N.currentSpeed.text.y),
              _.fillText(O("canvas.actualSpeed"),
                N.modbusSpeed.text.x,
                N.modbusSpeed.text.y),
              _.fillText(O("canvas.modbusSpeed"),
                N.modbusSpeedRPM.text.x,
                N.modbusSpeedRPM.text.y),
              _.textAlign = "right",
              _.fillText(`${V.value !== null ? V.value + "%" : O("canvas.none")}`,
                N.currentSpeed.value.x,
                N.currentSpeed.value.y),
              _.fillText(`${l.value !== null ? l.value + "%" : O("canvas.none")}`,
                N.modbusSpeed.value.x,
                N.modbusSpeed.value.y),
              _.fillText(`${c.value !== null ? c.value + " RPM" : O("canvas.none")}`,
                N.modbusSpeedRPM.value.x,
                N.modbusSpeedRPM.value.y)
          }
        };
      function n(o,
        u,
        d,
        Z,
        W,
        L,
        R,
        r = "",
        _ = "center") {
        o.save(),
          o.font = d,
          o.textBaseline = "center",
          o.textAlign = _,
          o.fillStyle = w.primary_25;
        const T = o.measureText(u).width,
          s = parseInt(d, 18),
          p = L - (T + 10) / 2,
          I = R - s / 2;
        _ === "left" ? f.value < 425 ? o.fillRect(5,
          I,
          T + 10,
          s) : f.value < 768 ? o.fillRect(10,
            I,
            T + 10,
            s) : o.fillRect(20,
              I,
              T + 10,
              s) : o.fillRect(p,
                I,
                T + 10,
                s),
          o.fillStyle = w.secondary_70;
        const S = p + (T + 10) / 2,
          P = R + s / 5;
        if (o.fillText(u,
          S,
          P),
          r) {
          let m = s / 2 + s / 3.5;
          window.innerWidth <= 600 && (m = s / 2 + s / 1.5),
            o.fillText(r,
              S,
              P + m)
        }
        o.restore()
      }
      return PA(() => {
        var o;
        return (o = cA().getModule(SA().params.moduleId)) == null ? void 0 : o.memory.memory
      }, () => {
        C()
      }, {
        deep: !0
      }),
        pA(async () => {
          window.addEventListener("resize",
            C),
            C()
        }),
        OA(() => window.removeEventListener("resize",
          C)), (o,
            u) => {
          const d = b("b-col"),
            Z = b("b-container");
          return F(),
            AA(d, {
              cols: 1,
              class: "tw-w-full tw-h-min chart-type-container tw-bg-primary_5"
            }, {
              default: Y(() => [J("div",
                hA,
                g(o.$t("parameters.USTAWIENIA_WENTYLATORA_F1")), 1),
              U(Z,
                null, {
                default: Y(() => [u[0] || (u[0] = J("div", {
                  class: "tw-flex tw-justify-center"
                }, [J("div", {
                  class: "tw-bg-background tw-rounded tw-m-2"
                }, [J("canvas", {
                  id: "my-canvas",
                  width: 400,
                  height: 200,
                  tabindex: "0"
                })])], -1)),
                U(d, {
                  class: "tw-gap-2 tw-m-2",
                  cols: 1,
                  lgCols: 2
                }, {
                  default: Y(() => [(F(!0),
                    sA(tA,
                      null,
                      IA([H(y),
                      H(h),
                      H(i),
                      H(k)],
                        W => (F(),
                          AA(H(z), {
                            parameter: W
                          },
                            null, 8, ["parameter"]))), 256))]),
                  _: 1
                }),
                U(d, {
                  class: "tw-m-2",
                  cols: 1
                }, {
                  default: Y(() => [U(H(z), {
                    parameter: H(B)
                  },
                    null, 8, ["parameter"])]),
                  _: 1
                })]),
                _: 1
              })]),
              _: 1
            })
        }
    }
  }),
  GA = {
    class: "tw-text-xl lg:tw-text-3xl tw-text-center tw-text-secondary tw-my-2"
  },
  fA = _A({
    __name: "GeneratorCurve",
    props: {
      parameters: {}
    },
    setup(eA) {
      const z = oA(() => iA(() => import("./pcDynamicParameterRecord-D_IQLH_6.js"),
        __vite__mapDeps([0, 1, 2]))),
        O = eA,
        w = EA(() => O.parameters.special.map(({
          parameter: t }) => t)), [f,
            K,
            v,
            V,
            l,
            c] = w.value,
        y = EA(() => {
          if (l.unit && "value" in l.unit && l.unit.value) return l.unit.value(Number(l.value))
        }),
        k = EA(() => {
          if (c.unit && "value" in c.unit && c.unit.value) return c.unit.value(Number(c.value))
        }), {
          colors: h } = TA.theme.global.current.value, {
            t: i } = MA(),
        B = () => {
          let t = document.getElementById("my-canvas"),
            n = document.getElementsByClassName("chart-type-container")[0].offsetWidth - 50;
          n > 820 && (n = 820);
          const o = n,
            u = n / 2.5;
          t.style.width = o + "px",
            t.style.height = u + "px";
          const d = window.devicePixelRatio;
          t.width = o * d,
            t.height = u * d;
          const {
            width: Z,
            height: W } = t.getBoundingClientRect();
          if (t.getContext) {
            const L = t.getContext("2d");
            L.scale(d,
              d);
            let R = "14px Arial";
            window.innerWidth <= 400 ? R = "6px Arial" : window.innerWidth <= 500 ? R = "8px Arial" : window.innerWidth <= 650 && (R = "10px Arial");
            const r = h.secondary_70,
              _ = h.primary_25,
              T = "#00e600";
            L.font = R,
              L.fillStyle = _;
            const s = {
              x1: Z * .15,
              y1: W * .13,
              x2: Z * .15,
              y2: W * .855,
              x3: Z * .82,
              y3: W * .85
            };
            L.beginPath(),
              L.moveTo(s.x1,
                s.y1),
              L.lineTo(s.x2,
                s.y2),
              L.lineTo(s.x3,
                s.y3),
              L.strokeStyle = r,
              L.lineWidth = 1,
              L.stroke(),
              L.closePath(),
              G(L,
                i("canvas.outdoorTemperature.short"),
                R, "#5b5b5b",
                r,
                s.x3,
                s.y3,
                void 0, "center"),
              G(L,
                i("canvas.coolingTemperature.short"),
                R, "#5b5b5b",
                r,
                s.x1,
                W * .1,
                void 0, "center");
            const p = s.y2 - s.y1,
              I = 30,
              S = x => p - x * p / I + W * .1,
              P = {
                p0: {
                  x: Z * .6,
                  y: S(Number(k.value))
                },
                p1: {
                  x: Z * .3,
                  y: S(Number(y.value))
                }
              };
            L.beginPath(),
              L.setLineDash([5, 4.2]),
              L.moveTo(s.x1,
                P.p0.y),
              L.lineTo(P.p0.x,
                P.p0.y),
              L.strokeStyle = r,
              L.stroke(),
              L.closePath(),
              L.beginPath(),
              L.setLineDash([5, 4.2]),
              L.moveTo(s.x1,
                P.p1.y),
              L.lineTo(P.p1.x,
                P.p1.y),
              L.strokeStyle = r,
              L.stroke(),
              L.closePath(),
              G(L, `${y.value}°C`,
                R, "#5b5b5b",
                r,
                s.x1 - s.x1 * .4,
                P.p1.y,
                void 0),
              L.fillStyle = _,
              L.beginPath();
            const m = Z * .015;
            L.rect(s.x1 - m / 2,
              P.p0.y - m / 2,
              m,
              m),
              L.fill(),
              L.fillStyle = _,
              L.beginPath(),
              L.rect(s.x1 - m / 2,
                P.p1.y - m / 2,
                m,
                m),
              L.fill(),
              G(L, `${k.value} °C`,
                R, "#5b5b5b",
                r,
                s.x1 - s.x1 * .4,
                P.p0.y),
              G(L, "20",
                R, "#5b5b5b",
                r,
                P.p1.x,
                s.y3 + s.y3 * .07,
                void 0, "center"),
              L.fillStyle = _,
              L.beginPath(),
              L.rect(P.p1.x - m / 2,
                s.y3 - m / 2,
                m,
                m),
              L.fill(),
              G(L, "35",
                R, "#5b5b5b",
                r,
                P.p0.x,
                s.y3 + s.y3 * .07,
                void 0, "center"),
              L.fillStyle = _,
              L.beginPath(),
              L.rect(P.p0.x - m / 2,
                s.y3 - m / 2,
                m,
                m),
              L.fill(),
              L.beginPath(),
              L.moveTo(P.p0.x,
                P.p0.y),
              L.lineTo(P.p0.x,
                P.p0.y),
              L.lineTo(P.p1.x,
                P.p1.y),
              L.strokeStyle = T,
              L.lineWidth = 1,
              L.stroke(),
              L.closePath();
            const X = Z * .0075,
              D = new Path2D;
            D.moveTo(P.p0.x,
              P.p0.y),
              D.arc(P.p0.x,
                P.p0.y,
                X, 0, 2 * Math.PI),
              L.fillStyle = T,
              L.fill(D),
              D.closePath(),
              G(L,
                i("canvas.maxCoolingTemperature.short"),
                R, "#5b5b5b",
                r,
                P.p0.x,
                P.p0.y + P.p0.y * -.2,
                void 0, "center");
            const N = new Path2D;
            N.moveTo(P.p1.x,
              P.p1.y),
              N.arc(P.p1.x,
                P.p1.y,
                X, 0, 2 * Math.PI),
              L.fillStyle = T,
              L.fill(N),
              N.closePath(),
              G(L,
                i("canvas.minCoolingTemperature.short"),
                R, "#5b5b5b",
                r,
                P.p1.x,
                P.p1.y + P.p1.y * -.25,
                void 0, "center")
          }
        };
      function G(t,
        C,
        n,
        o,
        u,
        d,
        Z,
        W = "",
        L = "center") {
        t.save(),
          t.font = n,
          t.textBaseline = "center",
          t.textAlign = L,
          t.fillStyle = h.primary_25;
        const R = t.measureText(C).width,
          r = parseInt(n, 18),
          _ = d - (R + 10) / 2,
          T = Z - r / 2;
        t.fillRect(_,
          T,
          R + 10,
          r),
          t.fillStyle = u;
        const s = _ + (R + 10) / 2,
          p = Z + r / 5;
        if (t.fillText(C,
          s,
          p),
          W) {
          let I = r / 2 + r / 3.5;
          window.innerWidth <= 600 && (I = r / 2 + r / 1.5),
            t.fillText(W,
              s,
              p + I)
        }
        t.restore()
      }
      return pA(() => {
        B(),
          window.addEventListener("resize",
            B)
      }),
        OA(() => window.removeEventListener("resize",
          B)),
        PA(() => {
          var t;
          return (t = cA().getModule(SA().params.moduleId)) == null ? void 0 : t.memory.memory
        }, () => {
          B()
        }, {
          deep: !0
        }), (t,
          C) => {
          const n = b("b-col"),
            o = b("b-container");
          return F(),
            AA(n, {
              cols: 1,
              class: "tw-w-full tw-h-min chart-type-container tw-bg-primary_5"
            }, {
              default: Y(() => [J("div",
                GA,
                g(t.$t("parameters.WYKRES_PRZEDSTAWIAJACY_KRZYWA_CHLODZENIA")), 1),
              U(o,
                null, {
                default: Y(() => [C[0] || (C[0] = J("div", {
                  class: "tw-flex tw-justify-center"
                }, [J("div", {
                  class: "tw-bg-background tw-rounded tw-m-2"
                }, [J("canvas", {
                  id: "my-canvas",
                  width: 400,
                  height: 200,
                  tabindex: "0"
                })])], -1)),
                U(n, {
                  class: "tw-gap-2 tw-m-2",
                  cols: 1,
                  lgCols: 2
                }, {
                  default: Y(() => [U(H(z), {
                    parameter: H(l)
                  },
                    null, 8, ["parameter"]),
                  U(H(z), {
                    parameter: H(c)
                  },
                    null, 8, ["parameter"])]),
                  _: 1
                })]),
                _: 1
              })]),
              _: 1
            })
        }
    }
  }),
  KA = {
    class: "tw-flex tw-justify-between tw-text-3xl tw-font-semibold"
  },
  bA = {
    class: "tw-text-lg"
  },
  gA = _A({
    __name: "PumpCirculationSchedule",
    props: {
      parameters: {}
    },
    setup(eA) {
      var G;
      const z = oA(() => iA(() => import("./PumpCirculationDay-DHRlPTuX.js"),
        __vite__mapDeps([3, 1, 2]))), {
          width: O } = mA(), {
            t: w } = MA(),
        f = eA,
        K = $(null),
        v = [{
          title: w("days.monday"),
          value: 0
        }, {
          title: w("days.tuesday"),
          value: 1
        }, {
          title: w("days.wednesday"),
          value: 2
        }, {
          title: w("days.thursday"),
          value: 3
        }, {
          title: w("days.friday"),
          value: 4
        }, {
          title: w("days.saturday"),
          value: 5
        }, {
          title: w("days.sunday"),
          value: 6
        }],
        V = $(j.map(j.cloneDeep((G = f.parameters.special) == null ? void 0 : G[0].parameter.value),
          t => j.remove(t, (C,
            n) => n % 2 === 0))),
        l = EA(() => O.value <= 1024),
        c = $(),
        y = t => {
          c.value = t
        },
        k = t => {
          K.value = t
        },
        h = t => {
          K.value && (V.value[t] = [...K.value])
        },
        i = () => {
          const t = j.map(V.value,
            C => j.flatMap(C,
              n => [n,
                n]));
          f.parameters.special[0].parameter.command && Array.isArray(f.parameters.special[0].parameter.command) && (f.parameters.special[0].parameter.command.map((C,
            n) => {
            Array.isArray(f.parameters.special[0].parameter.value) && !j.isEqual(f.parameters.special[0].parameter.value[n],
              t[n]) && CA.sendCommand(f.parameters.special[0].parameter,
                t[n],
                n).then(() => { }).catch(o => NA(o))
          }),
            UA({
              message: w("tariff.changesAddedToQueue"),
              icon: a.COMPLETE
            }))
        },
        B = () => {
          V.value = j.map(j.cloneDeep(f.parameters.special[0].parameter.value),
            t => j.remove(t, (C,
              n) => n % 2 === 0))
        };
      return (t,
        C) => {
        const n = b("b-button"),
          o = b("b-button-outline"),
          u = b("b-col"),
          d = b("b-expansion-panels"),
          Z = b("b-container");
        return F(),
          AA(u, {
            cols: 1,
            class: "tw-w-full tw-h-min"
          }, {
            default: Y(() => [U(Z,
              null, {
              default: Y(() => [U(u, {
                cols: 1,
                class: "tw-text-secondary tw-gap-2 tw-pb-6"
              }, {
                default: Y(() => [J("h2",
                  KA, [q(g(t.$t("modules.pumpCirculationSchedule.title")) + " ", 1),
                  l.value ? LA("", !0) : (F(),
                    AA(u, {
                      key: 0,
                      class: "tw-gap-4",
                      cols: 1,
                      lgCols: 2
                    }, {
                      default: Y(() => [U(n, {
                        onClick: i
                      }, {
                        default: Y(() => [q(g(t.$t("app.save")), 1)]),
                        _: 1
                      }),
                      U(o, {
                        onClick: C[0] || (C[0] = W => B())
                      }, {
                        default: Y(() => [q(g(t.$t("app.cancel")), 1)]),
                        _: 1
                      })]),
                      _: 1
                    }))]),
                J("p",
                  bA,
                  g(t.$t("modules.pumpCirculationSchedule.description")), 1),
                l.value ? (F(),
                  AA(u, {
                    key: 0,
                    class: "tw-gap-4",
                    cols: 1,
                    lgCols: 2
                  }, {
                    default: Y(() => [U(n, {
                      onClick: i
                    }, {
                      default: Y(() => [q(g(t.$t("app.save")), 1)]),
                      _: 1
                    }),
                    U(o, {
                      onClick: C[1] || (C[1] = W => B())
                    }, {
                      default: Y(() => [q(g(t.$t("app.cancel")), 1)]),
                      _: 1
                    })]),
                    _: 1
                  })) : LA("", !0)]),
                _: 1
              }),
              U(u, {
                cols: 1,
                class: "lg:tw-bg-primary_5 lg:tw-rounded-lg lg:tw-pb-4 tw-px-4"
              }, {
                default: Y(() => [U(d, {
                  class: "tw-mt-4 lg:!tw-w-4/5 without-border-radius lg:tw-divide-y lg:tw-divide-primary_25",
                  variant: "accordion",
                  modelValue: c.value, "onUpdate:modelValue": y
                }, {
                  default: Y(() => [(F(!0),
                    sA(tA,
                      null,
                      IA(V.value, (W,
                        L) => (F(),
                          AA(H(z), {
                            onOnPasteDay: h,
                            onOnCopyDay: k,
                            dayNumber: L,
                            copiedSchedule: K.value,
                            title: v[L].title,
                            schedule: W
                          },
                            null, 8, ["dayNumber", "copiedSchedule", "title", "schedule"]))), 256))]),
                  _: 1
                }, 8, ["modelValue"])]),
                _: 1
              })]),
              _: 1
            })]),
            _: 1
          })
      }
    }
  }),
  xA = "/assets/sch_do_automatyki-SkEmAtzk.svg",
  rA = "Manrope",
  aA = 1200,
  JA = _A({
    __name: "Schema",
    props: {
      parameters: {}
    },
    setup(eA) {
      const z = eA,
        O = EA(() => z.parameters.special.map(({
          parameter: R }) => R)),
        w = SA(),
        f = EA(() => w.params.moduleId), {
          colors: K } = TA.theme.global.current.value;
      let v = null;
      const V = $(null),
        l = $(null),
        c = $(0),
        y = $(0),
        k = $(null);
      let h = null,
        i = null,
        B = 0;
      const G = async (R,
        r) => {
        try {
          const _ = await fetch(R);
          if (!_.ok) throw new Error(`HTTP error! status: ${_.status}`);
          const s = (await _.text()).replace(/#1F1F1F/g,
            r),
            p = new Image,
            I = new Blob([s], {
              type: "image/svg+xml"
            }),
            S = URL.createObjectURL(I);
          p.onload = () => {
            k.value = p,
              URL.revokeObjectURL(S),
              t()
          },
            p.src = S
        }
        catch (_) {
          console.error(_)
        }
      },
        t = async () => {
          if (!l.value || !V.value || !k.value || !h) return;
          const R = l.value.getContext("2d");
          if (i = h.getContext("2d"), !R || !i) return;
          B++;
          const r = B,
            _ = V.value.getBoundingClientRect().width,
            T = k.value,
            s = T.naturalWidth,
            I = T.naturalHeight / s,
            S = _ * I,
            P = window.devicePixelRatio || 1;
          h.width = _ * P,
            h.height = S * P,
            c.value = _,
            y.value = S,
            i.resetTransform(),
            i.scale(P,
              P),
            i.clearRect(0, 0,
              c.value,
              y.value),
            i.drawImage(T, 0, 0,
              c.value,
              y.value);
          const m = W(r);
          await Promise.all(m),
            i.drawImage(T, 0, 0,
              c.value,
              y.value),
            L(),
            r === B && (l.value.width = h.width,
              l.value.height = h.height,
              l.value.style.width = `${_}
px`,
              l.value.style.height = `${S}
px`,
              R.drawImage(h, 0, 0))
        },
        C = R => {
          const r = O.value.find(p => p.id === Number(R)),
            _ = r == null ? void 0 : r.getParameterName();
          let T = r == null ? void 0 : r.getParameterValue(),
            s = r == null ? void 0 : r.getParameterValue({
              partial: !0
            });
          if (R === "OVERHEATING") {
            const p = O.value.find(S => S.id === 140137),
              I = O.value.find(S => S.id === 140115); (p == null ? void 0 : p.value) !== void 0 && (I == null ? void 0 : I.value) !== void 0 && (T = p == null ? void 0 : p.getParameterValue({
                value: p.value - I.value
              }),
                s = {
                  value: parseFloat(String(T))
                })
          }
          return {
            parameter: r,
            text: _,
            value: T,
            valuePartial: s
          }
        },
        n = (R,
          r,
          _) => {
          if (!_) return R;
          const T = new RegExp(`(<(?:g|path|rect|polygon|circle|line)[^>]*id="${r}"[^>]*>)`),
            s = R.match(T);
          if (!s) return console.warn(`Nie znaleziono elementu o id="${r}".`),
            R;
          const p = s[1],
            I = /class="[^"]*"/.test(p) ? p.replace('class="', `class="${_} `) : p.replace(">", ` class="${_}">`);
          return R.replace(p,
            I)
        },
        o = (R,
          r) => {
          if (!i) return;
          const _ = c.value,
            T = y.value,
            s = c.value / aA,
            p = ((r == null ? void 0 : r.size) ?? 14) * s;
          if (i.textAlign = (r == null ? void 0 : r.textAlign) ?? "start",
            i.font = `${p}
px ${rA}`,
            i.fillStyle = K.secondary_70,
            i.fillText(R,
              r.x * _,
              r.y * T),
            r.type !== void 0) {
            const I = r.x * _,
              S = (r.y - .0325) * T,
              P = .015 * _,
              m = .0175 * T;
            i.beginPath(),
              i.fillStyle = K.secondary_70,
              i.fillRect(I,
                S,
                P,
                m);
            const X = I + P / 2,
              D = S + m / 2;
            i.fillStyle = K.background;
            const N = 11 * s;
            i.font = `${N}
px ${rA}`,
              i.textAlign = "center",
              i.textBaseline = "middle",
              i.fillText(r.type,
                X,
                D)
          }
        },
        u = async (R,
          r,
          _) => {
          var m;
          if (!i || _ !== B) return;
          const T = r == null ? void 0 : r.value,
            s = c.value,
            p = y.value,
            I = c.value / aA,
            S = R.x * s,
            P = R.y * p;
          if (R.circle !== void 0 && (typeof R.circle.fillStyle == "string" ? i.fillStyle = R.circle.fillStyle : T in R.circle.fillStyle && (i.fillStyle = R.circle.fillStyle[T]),
            i.beginPath(),
            i.arc(S,
              P,
              R.circle.radius * I, 0, 2 * Math.PI),
            i.fill()),
            R.rect !== void 0) {
            typeof R.rect.fillStyle == "string" ? i.fillStyle = R.rect.fillStyle : T in R.rect.fillStyle && (i.fillStyle = R.rect.fillStyle[T]);
            const X = R.rect.width * I,
              D = R.rect.height * I,
              N = S - X / 2,
              x = P - D / 2;
            i.fillRect(N,
              x,
              X,
              D)
          }
          if (R.image !== void 0) {
            const X = new Image,
              D = R.image.maxWidth * I;
            let N = "";
            const x = R.image.class;
            x !== void 0 && (typeof x == "string" ? N = x : typeof x == "object" && T in x && (N = x[T]));
            try {
              const Q = await fetch(R.image.url);
              if (_ !== B) return;
              if (!Q.ok) throw new Error(`HTTP error! status: ${Q.status}`);
              const XA = await Q.text();
              if (_ !== B) return;
              const ZA = n(XA, "body",
                N);
              if (X.src = `data:image/svg+xml;
base64,${btoa(unescape(encodeURIComponent(ZA)))}`,
                await X.decode(),
                _ !== B) return;
              const nA = X.naturalWidth,
                lA = X.naturalHeight,
                DA = Math.min(D / nA,
                  D / lA),
                uA = nA * DA,
                dA = lA * DA;
              i.save(),
                i.translate(S,
                  P),
                i.rotate((((m = R.image) == null ? void 0 : m.rotate) ?? 0) * Math.PI / 180),
                i.drawImage(X, -uA / 2, -dA / 2,
                  uA,
                  dA),
                i.restore()
            }
            catch (Q) {
              console.error("Coś poszło nie tak przy pobieraniu lub modyfikacji SVG:",
                Q,
                R.image.url)
            }
          }
        },
        d = R => {
          if (!i) return;
          const r = c.value,
            _ = y.value,
            T = c.value / aA;
          var s = R.x * r,
            p = R.y * _,
            I = .225 * r,
            S = .03 * _,
            P = i.createLinearGradient(s, 0,
              s + I, 0);
          R.colors.forEach(X => {
            P.addColorStop(X.position,
              X.value)
          }),
            i.fillStyle = P,
            i.fillRect(s,
              p,
              I,
              S),
            i.fillStyle = K.secondary_70;
          const m = 10 * T;
          i.font = `${m}
px ${rA}`,
            i.textAlign = "center",
            R.values.stop.forEach(X => {
              let D = R.x * r + I * X.value;
              i.fillText(X.text,
                D, (R.y - .006) * _)
            })
        },
        Z = (R,
          r) => {
          if (!i) return;
          const _ = c.value,
            T = y.value,
            s = c.value / aA,
            p = .225 * _,
            I = .03 * T;
          let S = Math.abs(r.values.max - r.values.min),
            P = R - r.values.min,
            m = S > 0 ? P / S : 0;
          var X = r.x * _ + m * p,
            D = r.y * T;
          if (R >= r.values.min && R <= r.values.max) {
            i.beginPath(),
              i.moveTo(X,
                D),
              i.lineTo(X,
                D + I),
              i.lineWidth = 3,
              i.strokeStyle = "#f3f3f3",
              i.stroke();
            const N = 12 * s;
            i.font = `${N}
px ${rA}`,
              i.fillStyle = "#f3f3f3",
              i.fillText(Number(R).toFixed(1),
                X,
                D + I + 15 * s)
          }
        },
        W = R => {
          if (!i) return [];
          const r = [];
          for (const [_,
            T] of Object.entries(VA)) {
            const {
              parameter: s,
              value: p } = C(_);
            T != null && T.drawer && r.push(u(T.drawer,
              s,
              R));
            const I = [(T == null ? void 0 : T.value) || []].flat();
            for (const S of I) if ("rect" in S && S.rect) {
              const P = S.rect.find(m => m.expectedValue === p);
              P && r.push(u(P, {
                value: 0
              },
                R))
            }
          }
          return r
        },
        L = R => {
          if (i) for (const [r,
            _] of Object.entries(VA)) {
            const {
              text: T,
              value: s,
              valuePartial: p } = C(r),
              I = [(_ == null ? void 0 : _.text) || []].flat(),
              S = [(_ == null ? void 0 : _.value) || []].flat(),
              P = _ == null ? void 0 : _.gradient;
            for (const m of I) o(m != null && m.overwrite ? YA(m.overwrite,
              f.value) : T ?? "app.unknown",
              m);
            for (const m of S) o(m != null && m.overwrite ? YA(m.overwrite,
              f.value) : String(s ?? ""),
              m);
            P !== void 0 && (d(P),
              Z(Number((p == null ? void 0 : p.value) ?? 0),
                P))
          }
        };
      return pA(() => {
        h = document.createElement("canvas"),
          G(xA,
            K.secondary_70),
          V.value && (v = new ResizeObserver(t),
            v.observe(V.value))
      }),
        vA(() => {
          v && V.value && (v.unobserve(V.value),
            v.disconnect()),
            h = null
        }),
        PA(() => z.parameters, () => {
          k.value && t()
        }, {
          deep: !0
        }), (R,
          r) => (F(),
            sA("div", {
              ref_key: "canvasContainer",
              ref: V,
              class: "tw-w-full tw-rounded tw-bg-primary_5"
            }, [J("canvas", {
              ref_key: "canvas",
              ref: l,
              style: {
                display: "block"
              }
            }, [J("p",
              null,
              g(R.$t("module.schema.canvasNotSupported")), 1)], 512)], 512))
    }
  }),
  HA = {
    class: "tw-flex tw-items-center tw-justify-between tw-text-3xl tw-font-semibold"
  },
  FA = {
    class: "tw-text-lg"
  },
  kA = {
    class: "tw-bg-primary_5 tw-rounded-lg tw-text-center tw-flex tw-flex-col tw-py-4 lg:tw-py-0 tw-gap-2 lg:tw-items-center lg:tw-pt-6"
  }, $A = _A({
    __name: "Tariffs",
    props: {
      parameters: {}
    },
    setup(eA) {
      const z = oA(() => iA(() => import("./TariffDay-BdHISs4R.js"),
        __vite__mapDeps([4, 1, 2]))), {
          t: O } = MA(), {
            width: w } = mA(),
        f = $({
          value: 0,
          index: 0
        }),
        K = EA(() => w.value <= 1024),
        v = eA,
        V = $(v.parameters.read[0].parameter.value),
        l = $(Object.assign({
          [RA.USR]: {
            isEditable: !0,
            days: [...v.parameters.special[0].parameter.value]
          }
        }, ...Object.entries(WA).map(([o,
          u]) => ({
            [o]: {
              isEditable: !1,
              days: u
            }
          })))),
        c = EA(() => Object.keys(l.value).map(o => ({
          title: o,
          value: o,
          callback: u => {
            V.value = u.value
          }
        }))),
        y = $(null),
        k = [{
          title: O("days.monday"),
          value: 0
        }, {
          title: O("days.tuesday"),
          value: 1
        }, {
          title: O("days.wednesday"),
          value: 2
        }, {
          title: O("days.thursday"),
          value: 3
        }, {
          title: O("days.friday"),
          value: 4
        }, {
          title: O("days.saturday"),
          value: 5
        }, {
          title: O("days.sunday"),
          value: 6
        }],
        h = (o,
          u) => {
          V.value !== RA.USR && (l.value.USR.days = [...l.value[V.value].days]),
            V.value = RA.USR,
            l.value.USR.days = [...l.value.USR.days.map((d,
              Z) => {
              if (Z === o) {
                const W = d.filter((L,
                  R) => R % 2);
                return W[u.index] = u.value,
                  j.flatMap(W,
                    L => [L,
                      L])
              }
              return d
            })]
        },
        i = o => {
          y.value = l.value.USR.days[o]
        },
        B = o => {
          y.value && (l.value.USR.days[o] = y.value)
        },
        G = $(),
        t = o => {
          G.value = o
        },
        C = () => {
          !v.parameters.special[0].parameter.command || !Array.isArray(v.parameters.special[0].parameter.command) || (v.parameters.special[0].parameter.command.map((o,
            u) => {
            Array.isArray(v.parameters.special[0].parameter.value) && !j.isEqual(v.parameters.special[0].parameter.value[u],
              l.value[V.value].days[u]) && CA.sendCommand(v.parameters.special[0].parameter,
                l.value[V.value].days[u],
                u).then(() => { }).catch(d => NA(d))
          }),
            UA({
              message: O("tariff.changesAddedToQueue"),
              icon: a.COMPLETE
            }))
        },
        n = () => {
          l.value.USR.days = [...v.parameters.special[0].parameter.value]
        };
      return PA(l, () => {
        const o = Object.entries(WA).find(([u,
          d]) => j.isEqual(l.value.USR.days,
            d));
        o && (V.value = o[0])
      }, {
        immediate: !0,
        deep: !0
      }), (o,
        u) => {
          const d = b("b-button"),
            Z = b("b-button-outline"),
            W = b("b-col"),
            L = b("b-label"),
            R = b("b-tabs-small"),
            r = b("b-expansion-panels"),
            _ = b("b-container");
          return F(),
            AA(W, {
              cols: 1,
              class: "tw-w-full tw-h-min"
            }, {
              default: Y(() => [U(_,
                null, {
                default: Y(() => [U(W, {
                  cols: 1,
                  class: "tw-text-secondary tw-gap-2 tw-pb-6"
                }, {
                  default: Y(() => [J("h2",
                    HA, [q(g(o.$t("routes.modules.moduleTariff")) + " ", 1),
                    K.value ? LA("", !0) : (F(),
                      AA(W, {
                        key: 0,
                        class: "tw-gap-4",
                        cols: 1,
                        lgCols: 2
                      }, {
                        default: Y(() => [U(d, {
                          onClick: C
                        }, {
                          default: Y(() => [q(g(o.$t("app.save")), 1)]),
                          _: 1
                        }),
                        U(Z, {
                          onClick: n
                        }, {
                          default: Y(() => [q(g(o.$t("app.cancel")), 1)]),
                          _: 1
                        })]),
                        _: 1
                      }))]),
                  J("p",
                    FA,
                    g(o.$t("modules.tariffsDescription")), 1),
                  K.value ? (F(),
                    AA(W, {
                      key: 0,
                      class: "tw-gap-4",
                      cols: 1,
                      lgCols: 2
                    }, {
                      default: Y(() => [U(d, {
                        onClick: C
                      }, {
                        default: Y(() => [q(g(o.$t("app.save")), 1)]),
                        _: 1
                      }),
                      U(Z, {
                        onClick: n
                      }, {
                        default: Y(() => [q(g(o.$t("app.cancel")), 1)]),
                        _: 1
                      })]),
                      _: 1
                    })) : LA("", !0)]),
                  _: 1
                }),
                U(W, {
                  cols: 1,
                  class: "lg:tw-bg-primary_5 lg:tw-rounded-lg lg:tw-pb-4 lg:tw-px-4"
                }, {
                  default: Y(() => [J("div",
                    kA, [U(L, {
                      class: "lg:tw-w-fit lg:tw-normal-case lg:tw-text-base"
                    }, {
                      default: Y(() => [q(g(o.$t("modules.selectTariff")), 1)]),
                      _: 1
                    }),
                    U(R, {
                      selectedItem: V.value,
                      items: c.value
                    },
                      null, 8, ["selectedItem", "items"])]),
                  U(r, {
                    class: "tw-mt-4 lg:!tw-w-4/5 without-border-radius lg:tw-divide-y lg:tw-divide-primary_25",
                    variant: "accordion",
                    modelValue: G.value, "onUpdate:modelValue": t
                  }, {
                    default: Y(() => [(F(),
                      sA(tA,
                        null,
                        IA(k, (T,
                          s) => U(H(z), {
                            startHour: f.value,
                            dayName: T.title,
                            day: T.value,
                            scheduleName: V.value,
                            schedule: l.value[V.value].days.map(p => p.filter((I,
                              S) => S % 2)),
                            hasCopiedDay: V.value === H(RA).USR ? !!y.value : void 0,
                            isEditable: l.value[V.value].isEditable,
                            onOnCopyDay: i,
                            onOnPasteDay: B,
                            onOnHourStateChange: p => h(s,
                              p)
                          },
                            null, 8, ["startHour", "dayName", "day", "scheduleName", "schedule", "hasCopiedDay", "isEditable", "onOnHourStateChange"])), 64))]),
                    _: 1
                  }, 8, ["modelValue"])]),
                  _: 1
                })]),
                _: 1
              })]),
              _: 1
            })
        }
    }
  }),
  M = {
    FanViewerView: BA,
    GeneratorCurveView: fA,
    ParametersView: yA,
    PumpCirculationSchedule: gA,
    SchemaView: JA,
    TariffsView: $A
  },
  zA = [{
    path: "dhw",
    name: "modules.menu.dhw",
    meta: {
      displayName: "routes.modules.menu.dhw",
      icon: a.FAUCET,
      permissionModule: A.DISPLAY_MENU_DHW,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "AKTUALNA_TEMP_CWU_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "MOC_PID_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "AKTUALNA_MOC_GRZANIA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "COP_GRZANIE_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "AKTUALNA_TARYFA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "POZA_TARYFA")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TRYB_PRZYGOTOWANIA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "NASTAWA_W_TRYBIE_KOMFORTU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "NASTAWA_W_TRYBIE_EKONOMICZNYM_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "NASTAWA_W_TRYBIE_OCHRONY_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "HISTEREZA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRIORYTET_CWU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "DZIEN_DEZYNFEKCJI_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "GODZINA_DEZYNFEKCJI_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "DEZYNFEKCJA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "TRYB_IMPREZA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "CZAS_TRWANIA_TRYBU_IMPREZA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "NASTAWA_W_TRYBIE_IMPREZA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PODGRZEWANIE_CWU_PRZED_KONCEM_TARYFY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZAS_PODGRZEWANIA_CWU_PRZED_KONCEM_TARYFY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "ZALACZANIE_GRZALEK_DLA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "RODZAJ_GRZALEK_DLA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MAKSYMALNY_CZAS_PRACY_GRZALEK_PRZYPLYWOWYCH_DLA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MAKSYMALNY_CZAS_PRACY_GRZALKI_NURNIKOWEJ_DLA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "NASTAWA_DEZYNFEKCJI")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZAS_DETEKCJI_OGRANICZENIA_TEMPERATURY_ZASILANIA")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "circuits",
    name: "modules.menu.circuits",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.circuits",
      icon: a.CIRCUIT,
      permissionModule: A.DISPLAY_MENU_CIRCUITS
    },
    children: [{
      path: "ch0",
      name: "modules.menu.circuit.ch0",
      meta: {
        displayName: "routes.modules.menu.circuit.ch0",
        icon: a.CIRCUIT,
        permissionModule: A.DISPLAY_MENU_CIRCUIT_CH0,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WEW_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WYLICZANA_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "KG_AKTUALNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "TEMP_POWROTU_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "T_ZEWNETRZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_PID_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "AKTUALNA_MOC_GRZANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_CHLODZENIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "COP_GRZANIE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "COP_CHLODZENIE_READ")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "WARTOSC_OBNIZENIA_POZA_TARYFA_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "OBNIZENIE_NASTAWY_CO0_W_TRYBIE_URLOP_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "ZADANA_TEMP_CO0_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "NUMER_KRZYWEJ_GRZEWCZEJ_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "PRZESUNIECIE_KRZYWEJ_GRZEWCZEJ_OBIEG_CO_0_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KOREKTA_KRZYWEJ_GRZEWCZEJ__OBIEG_CO_0__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "NUMER_KRZYWEJ_CHLODNICZEJ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "PRZESUNIECIE_KRZYWEJ_CHLODNICZEJ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KOREKTA_KRZYWEJ_CHLODNICZEJ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MAKSYMALNA_TEMP_WODY_INSTALACYJNEJ__OBIEG_CO_0__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MINIMALNA_TEMP_WODY_INSTALACYJNEJ_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "UKLAD_GRZEJNIKOWY_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "TERMOSTAT_POKOJOWY_OBIEGU_CO0_WRITE")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_PV_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "ch1",
      name: "modules.menu.circuit.ch1",
      meta: {
        displayName: "routes.modules.menu.circuit.ch1",
        icon: a.CIRCUIT,
        permissionModule: A.DISPLAY_MENU_CIRCUIT_CH1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WEW_CO1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WYLICZANA_CO1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "KG_AKTUALNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "TEMP_OBIEGU_CO1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "T_ZEWNETRZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_PID_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "AKTUALNA_MOC_GRZANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_CHLODZENIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "COP_GRZANIE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "COP_CHLODZENIE_READ")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "WARTOSC_OBNIZENIA_POZA_TARYFA__OBIEG_CO_1__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "OBNIZENIE_NASTAWY_CO1_W_TRYBIE_URLOP_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "ZADANA_TEMP_CO1_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "NUMER_KRZYWEJ_GRZEWCZEJ__OBIEG_CO_1__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "PRZESUNIECIE_KRZYWEJ_GRZEWCZEJ__OBIEG_CO_1__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KOREKTA_KRZYWEJ_GRZEWCZEJ_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "NUMER_KRZYWEJ_CHLODNICZEJ_CO1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "PRZESUNIECIE_KRZYWEJ_CHLODNICZEJ_CO1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KOREKTA_KRZYWEJ_CHLODNICZEJ_CO1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MAKSYMALNA_TEMP_WODY_INSTALACYJNEJ_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MINIMALNA_TEMP_WODY_INSTALACYJNEJ__OBIEG_CO_1__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "UKLAD_GRZEJNIKOWY_CO1_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "TERMOSTAT_POKOJOWY_OBIEGU_CO1_WRITE")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_PV_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "ch2",
      name: "modules.menu.circuit.ch2",
      meta: {
        displayName: "routes.modules.menu.circuit.ch2",
        icon: a.CIRCUIT,
        permissionModule: A.DISPLAY_MENU_CIRCUIT_CH2,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WEW_CO2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WYLICZANA_CO2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "KG_AKTUALNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_OBIEGU_CO2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_PID_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "AKTUALNA_MOC_GRZANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_CHLODZENIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "COP_GRZANIE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "COP_CHLODZENIE_READ")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "WARTOSC_OBNIZENIA_POZA_TARYFA__OBIEG_CO_2__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "OBNIZENIE_NASTAWY_CO2_W_TRYBIE_URLOP_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "ZADANA_TEMP_CO2_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "NUMER_KRZYWEJ_GRZEWCZEJ__OBIEG_CO_2__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "PRZESUNIECIE_KRZYWEJ_GRZEWCZEJ__OBIEG_CO_2__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KOREKTA_KRZYWEJ_GRZEWCZEJ__OBIEG_CO_2__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "NUMER_KRZYWEJ_CHLODNICZEJ_CO2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "PRZESUNIECIE_KRZYWEJ_CHLODNICZEJ_CO2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KOREKTA_KRZYWEJ_CHLODNICZEJ_CO2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MAKSYMALNA_TEMP_WODY_INSTALACYJNEJ__OBIEG_CO_2__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MINIMALNA_TEMP_WODY_INSTALACYJNEJ__OBIEG_CO_2__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "UKLAD_GRZEJNIKOWY__OBIEG_CO_2__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "TERMOSTAT_POKOJOWY_OBIEGU_CO2_WRITE")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO_2_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P2_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB2_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_PV_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "ct",
      name: "modules.menu.circuit.ct",
      meta: {
        displayName: "routes.modules.menu.circuit.ct",
        icon: a.CIRCUIT,
        permissionModule: A.DISPLAY_MENU_CIRCUIT_CT,
        parameters: {
          read: [],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "ZADANA_TEMP_CWU_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "NUMER_KRZYWEJ_GRZEWCZEJ__OBIEG_CT__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "PRZESUNIECIE_KRZYWEJ_GRZEWCZEJ__OBIEG_CT__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "ZADANA_TEMP_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KOREKTA_KRZYWEJ_GRZEWCZEJ__OBIEG_CT__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MAKSYMALNA_TEMP_WODY_INSTALACYJNEJ__OBIEG_CT__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MINIMALNA_TEMP_WODY_INSTALACYJNEJ__OBIEG_CT__WRITE")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }]
  }, {
    path: "heaters",
    name: "modules.menu.heaters",
    meta: {
      displayName: "routes.modules.menu.heaters",
      icon: a.HEATERS,
      permissionModule: A.DISPLAY_MENU_HEATERS,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "OBECNA_MOC_GRZALEK_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_POWROTU_A1_T3_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "OBROTY_SPREZARKI_READ")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TRYB_MAKSYMALNY_MAKSYMALNA_MOC_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PUNKT_ROWNOWAGI_GRZALEK_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_POWROTU_MINIMUM_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEPLYW_MINIMALNY_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZAS_DETEKCJI_WZROSTU_TEMPERATURY_ZASILANIA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZAS_PRZELACZENIA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "GRZALKI_W_TRYBIE_OCZEKUJE_WRITE")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "cooling",
    name: "modules.menu.cooling",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.cooling",
      icon: a.COOLING,
      permissionModule: A.DISPLAY_MENU_COOLING
    },
    children: [{
      path: "setup",
      name: "modules.menu.cooling_setup",
      meta: {
        displayName: "routes.modules.menu.cooling_setup",
        icon: a.COOLING,
        permissionModule: A.DISPLAY_MENU_COOLING_SETUP,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZADANA_CHLODZENIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WEW_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WEW_CO1_READ")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "TRYB_CHLODZENIA_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "MINIMALNA_TEMPERATURA_POWIETRZA_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "ODWRACANIE_OBIEGU_DLA_CHLODZENIA")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_PV_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "curve",
      name: "modules.menu.cooling_curve",
      meta: {
        displayName: "routes.modules.menu.cooling_curve",
        icon: a.CURVE,
        permissionModule: A.DISPLAY_MENU_COOLING_CURVE,
        parameters: {
          read: [],
          write: [],
          status: [],
          special: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZADANA_CHLODZENIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_WEW_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PID_TI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "T_CHLOD_DLA_TEMPERATURY_ZEWNETRZNEJ_20_STOPNI")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "T_CHLOD_DLA_TEMPERATURY_ZEWNETRZNEJ_35_STOPNI")
          }]
        }
      },
      component: M.GeneratorCurveView
    }]
  }, {
    path: "defrost",
    name: "modules.menu.defrost",
    meta: {
      displayName: "routes.modules.menu.defrost",
      icon: a.DEFROST,
      permissionModule: A.DISPLAY_MENU_DEFROST,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "WSPOLCZYNNIK_I_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "RECZNA_INICJALIZACJA_DEFROSTU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "GRZALKI_PODCZAS_DEFROSTU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PUNKT_ROWNOWAGI_GRZALEK__DEFROST__WRITE")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "pumps",
    name: "modules.menu.pumps",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.pumps",
      icon: a.PUMP,
      permissionModule: A.DISPLAY_MENU_PUMPS
    },
    children: [{
      path: "p0",
      name: "modules.menu.pump.p0",
      meta: {
        displayName: "routes.modules.menu.pump.p0",
        icon: a.PUMP,
        permissionModule: A.DISPLAY_MENU_PUMP_P0,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ODCZYT_PWM_P0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "DELTA_TZAS_TPOW_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "DELTA_TZAS_TPOW__POMPA_P0__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CZAS_PRACY_POMPY_P0")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CZAS_PAUZY_POMPY_P0")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "ODPOWIETRZENIE__POMPA_P0__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "OBIEG_CWU_ODPOWIETRZANIE_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CZAS_ODPOWIETRZANIA_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "GLOBALNY_PRZELYW_MINIMALNY")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "HISTEREZA_DLA_MINIMALNEGO_PRZEPLYWU_P0")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "OGRANICZENIE_MAKSYMALNEGO_PRZEPLYWU_P0")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "TYP_POMPY_P0")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_PV_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "p1",
      name: "modules.menu.pump.p1",
      meta: {
        displayName: "routes.modules.menu.pump.p1",
        icon: a.PUMP,
        permissionModule: A.DISPLAY_MENU_PUMP_P1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ODCZYT_PWM_P1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "DELTA_TZAS_TPOW__POMPA_P1__READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "DELTA_TZAS_TPOW__POMPA_P1__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CZAS_PRACY_POMPY_P1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CZAS_PAUZY_POMPY_P1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "ODPOWIETRZENIE_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CZAS_ODPOWIETRZANIA__POMPA_P1__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "PRZEPLYW_MINIMALNY__POMPA_P1__WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "HISTEREZA_DLA_MINIMALNEGO_PRZEPLYWU_P1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "POMPA_Z_IPWM")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "TYP_POMPY_P1")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_PV_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "circulation",
      name: "modules.menu.pump.circulation",
      meta: {
        displayName: "routes.modules.menu.pump.circulation",
        icon: a.PUMP,
        permissionModule: A.DISPLAY_MENU_PUMP_CIRCULATION,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "AKTUALNA_TEMP_CWU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CYRKULACJA_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CZAS_POSTOJU_POMPY_CYRKULACYJNEJ_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "CZAS_PRACY_POMPY_CYRKULACYJNEJ_WRITE")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_PV_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "circulation/schedule",
      name: "modules.menu.pump.circulationSchedule",
      meta: {
        displayName: "routes.modules.menu.pump.circulationSchedule",
        icon: a.SCHEDULES,
        permissionModule: A.DISPLAY_MENU_PUMP_CIRCULATION_SCHEDULE,
        parameters: {
          read: [],
          write: [],
          status: [],
          special: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.SPECIAL, "HARMONOGRAM_PRACY_POMPY_CYRKULACYJNEJ")
          }]
        }
      },
      component: M.PumpCirculationSchedule
    }]
  }, {
    path: "flows",
    name: "modules.menu.flows",
    meta: {
      displayName: "routes.modules.menu.flows",
      icon: a.FLOWS,
      permissionModule: A.DISPLAY_MENU_FLOWS,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_CALKOWITY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_SIKA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_IPWM_P0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_IPWM_P1")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "GLOBALNY_PRZELYW_MINIMALNY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEPLYW_MINIMALNY_DLA_GRZALEK")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEPLYW_MINIMALNY_DLA_ODSZRANIANIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEPLYW_MINIMALNY_W_TRYBIE_BEZCZYNNOSCI")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "HISTEREZA_DLA_MINIMALNEGO_PRZEPLYWU_P0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "HISTEREZA_DLA_MINIMALNEGO_PRZEPLYWU_P1")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "compressor",
    name: "modules.menu.compressor",
    meta: {
      displayName: "routes.modules.menu.compressor",
      icon: a.COMPRESSOR,
      permissionModule: A.DISPLAY_MENU_COMPRESSOR,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PID_KP_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PID_TI_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "MOC_POMPY_CIEPLA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "AKTUALNA_MOC_GRZANIA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "MOC_CHLODZENIA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "MOC_PID_READ")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PID_KP_0_7_C_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PID_TI_0_7_C_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PID_KP_7_14_C_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PID_TI_7_14_C_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PID_KP_14_C_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PID_TI_14_C_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PID_KP_CHLODZENIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PID_TI_CHLODZENIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CWU_MIN_WYDAJNOSC_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OCHRONA_SKRAPLACZA_TZS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OCHRONA_SKRAPLACZA_T1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_OCHRONY_SKRAPLACZA_DEFROST_MIN10C")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_OCHRONY_SKRAPLACZA_DEFROST_PLUS3C")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "HISTEREZA_TEMPERATURY_OCHRONY_SKRAPLACZA_DEFROST")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZAS_DETEKCJI_ZMIANY_TEMPERATURY_DEFROST")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CWU_OBN_M_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "KP_T_PAR_MIN_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "KP_CAPACITY_MIN__500W_WRITE")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "schedules",
    name: "modules.menu.schedules",
    meta: {
      displayName: "routes.modules.menu.schedules",
      icon: a.SCHEDULES,
      permissionModule: A.DISPLAY_MENU_SCHEDULES,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "AKTUALNA_TARYFA_READ")
        }],
        write: [],
        status: [],
        special: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.SPECIAL, "TARYFY")
        }]
      }
    },
    component: M.TariffsView
  }, {
    path: "fan",
    name: "modules.menu.fan",
    meta: {
      displayName: "routes.modules.menu.fan",
      icon: a.FAN,
      permissionModule: A.DISPLAY_MENU_FAN,
      parameters: {
        read: [],
        write: [],
        status: [],
        special: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "ZADANE_OBROTY_WENTYLATORA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OBROTY_WENTYLATORA_MODBUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "AKTUALNE_OBROTY_WENTYLATORA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "REG1_REG3")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MANUALNA_PREDKOSC_WENTYLATORA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "ZALACZENIE_MANUALNEJ_PREDKOSCI_WENTYLATORA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "WSPOLCZYNNIK_KOREKTY_WENTYLATORA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "KOREKTA_MAKSYMALNEJ_WYDAJNOSCI_WENTYLATORA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MAKSYMALNA_WYDAJNOSC_WENTYLATORA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MINIMALNA_WYDAJNOSC_WENTYLATORA")
        }]
      }
    },
    component: M.FanViewerView
  }, {
    path: "test-and-calibration",
    name: "modules.menu.tests_and_calibration",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.tests_and_calibration",
      icon: a.PLUS_MINUS,
      permissionModule: A.DISPLAY_MENU_TESTS_AND_CALIBRATION
    },
    children: [{
      path: "calibration",
      name: "modules.menu.calibration",
      meta: {
        displayName: "routes.modules.menu.calibration",
        icon: a.PLUS_MINUS,
        permissionModule: A.DISPLAY_MENU_CALIBRATION,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T3")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T4")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T5")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T6")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T7")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T8")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T9")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T10")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T1_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T2_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T3_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T4_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T5_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T6_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T7_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T8_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T9_WRITE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "KALIBRACJA_T10_WRITE")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "PRACA_PV_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "test-output-input",
      name: "modules.menu.tests_output_input",
      meta: {
        displayName: "routes.modules.menu.tests_output_input",
        icon: a.DIP_SWITCH,
        permissionModule: A.DISPLAY_MENU_TESTS_OUTPUT_INPUT,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T3")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T4")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T5")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T6")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T7")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T8")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T9")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_A1_T10")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_SIKA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_PWM1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_PWM2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I1_CT_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I2_PV_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I3_CWU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I4_TAR_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I5_W1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I6_W2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I7_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I8_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIE_I9_READ")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "URUCHOMIENIE_POMPY_CIEPLA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "URUCHOMIENIE_TRYBU_TESTOWEGO")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "M0_ZAWOR_PRZELACZNY_CO_CWU")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "P0_POMPA_OBIEGU_CO0")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "M1_ZAWOR_OBIEGU_CO1_OTWIERANIE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "M1_ZAWOR_OBIEGU_CO1_ZAMYKANIE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "P1_POMPA_OBIEGU_CO1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "G1_GRZALKA_1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "G2_GRZALKA_2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "G5_POMPA_CYRKULACYJNA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "P4_POMPA_CT")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "P3_POMPA_3")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "S1_WYJSCIE")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "EM_EXV_ZAL_WYL")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "EM_EXV_REGULACJA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "EM_EXV_ZAL_WYL_2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "EM_EXV_REGULACJA_2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "EM_WENTYLATOR_ZAL_WYL")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.WRITE, "EM_WENTYLATOR_REGULACJA")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }]
  }, {
    path: "photovoltaics",
    name: "modules.menu.photovoltaics",
    meta: {
      displayName: "routes.modules.menu.photovoltaics",
      icon: a.PHOTOVOLTAICS,
      permissionModule: A.DISPLAY_MENU_PHOTOVOLTAICS,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PRZEWYZSZENIE_CWU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PRZEWYZSZENIE_CO0_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PRZEWYZSZENIE_CO1_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PRZEWYZSZENIE_CO2_WRITE")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEWYZSZENIE_CWU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEWYZSZENIE_CO0_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEWYZSZENIE_CO1_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEWYZSZENIE_CO2_WRITE")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "sg-ready",
    name: "modules.menu.sg_ready",
    meta: {
      displayName: "routes.modules.menu.sg_ready",
      icon: a.SG_READY,
      permissionModule: A.DISPLAY_MENU_SG_READY,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_CWU_TRYB_PODWYZSZONY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_CWU_TRYB_WYMUSZAJACY_WLACZENIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_CO0_TRYB_PODWYZSZONY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_CO0_TRYB_WYMUSZAJACY_WLACZENIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_CO1_TRYB_PODWYZSZONY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_CO1_TRYB_WYMUSZAJACY_WLACZENIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_CO2_TRYB_PODWYZSZONY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_CO2_TRYB_WYMUSZAJACY_WLACZENIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_BASENU_TRYB_PODWYZSZONY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_PRZEWYZSZENIE_BASENU_TRYB_WYMUSZAJACY_WLACZENIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_OBNIZENIE_CHLODZENIA_TRYB_PODWYZSZONY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SG_READY_OBNIZENIE_CHLODZENIA_TRYB_WYMUSZAJACY_WLACZENIE")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "operating-mode",
    name: "modules.menu.operating_mode",
    meta: {
      displayName: "routes.modules.menu.operating_mode",
      icon: a.CONFIGURATION,
      permissionModule: A.DISPLAY_MENU_OPERATING_MODE,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO1_READ")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "TRYB_PRACY_ZIMA_LATO_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PUNKT_ROWNOWAGI_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "HISTEREZA_PUNKTU_ROWNOWAGI_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "Z_ILU_GODZIN_SREDNIA_TEMPERATURY_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "TRYB_URLOP_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "CZAS_ZAKONCZENIA_TRYBU_URLOP_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "OBNIZENIE_NASTAWY_CO0_W_TRYBIE_URLOP_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "OBNIZENIE_NASTAWY_CO1_W_TRYBIE_URLOP_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OBNIZENIE_NASTAWY_CO2_W_TRYBIE_URLOP_WRITE")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "configuration",
    name: "modules.menu.configuration",
    meta: {
      displayName: "routes.modules.menu.configuration",
      icon: a.CONFIGURATION,
      permissionModule: A.DISPLAY_MENU_CONFIGURATION,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "MOC_POMPY_CIEPLA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "RODZAJ_POMPY_CIEPLA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "RODZAJ_WENTYLATORA")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TRYB_PRACY_CWU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRIORYTET_CWU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "DEZYNFEKCJA_CWU_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OBIEG_CO0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OBNIZENIE_POZA_TARYFA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_WEW_CO0_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "UKLAD_GRZEJNIKOWY_CO0_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OBIEG_CO1_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_WEWNETRZNA_CO1_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "UKLAD_GRZEJNIKOWY_CO1_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TRYB_CHLODZENIA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "FOTOWOLTAIKA_PV_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "GRZALKI_GR_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TRYB_AWARYJNY_GRZALEK_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "BLOKADA_SPREZARKI_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CIEPLO_TECHNOLOGICZNE_CT_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZUJNIK_TZEW_Z_T6_JEDNOSTKA_ZEWNETRZNA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZUJNIK_TZEW_Z_T8_JEDNOSTKA_WEWNETRZNA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_BUFORA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZELACZENIE_ZAWORU_MO_W_TRYBIE_LATO")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "WYJSCIE_S1_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_BIWALENTNA_ZC")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_BEZWZGLEDNA_ZC")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MINIMALNY_CZAS_PRACY_ZC")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OGRANICZNIK_TEMPERATURY_ZASILANIA_DLA_ZC")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "HISTEREZA_TEMPERATURY_ZASILANIA_DLA_ZC")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZAS_DETEKCJI_WZROSTU_TEMPERATURY_ZASILANIA_DLA_ZC")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "COMFORT_2_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "RODZAJ_JEDNOSTKI_WEWNETRZNEJ")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO_2_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "producer",
    name: "modules.menu.producer",
    meta: {
      displayName: "routes.modules.menu.producer",
      icon: a.CONFIGURATION,
      permissionModule: A.DISPLAY_MENU_PRODUCER,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "AKTUALNE_OBROTY_WENTYLATORA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "OBROTY_SPREZARKI_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "MOC_POMPY_CIEPLA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "RODZAJ_POMPY_CIEPLA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "RODZAJ_WENTYLATORA")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "ZAWARTOSC_REJESTRU_163_A2")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "COMFORT_2_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MANUAL_CAPACITY_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "ZALACZENIE_MANUAL_CAPACITY_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "NUMER_PARAMETRU_MODBUS_A2_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "WARTOSC_PARAMETRU_MODBUS_A2_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "POMIAR_PRZEPLYWU_CO0_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TYP_POMPY_P0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TYP_POMPY_P1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "KASUJ_HASLO_INSTALATORA_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEPLYW_MANUALNY_POMPY_P0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "RECZNA_REGULACJA_OBROTOW_WENTYLATORA_W0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "RECZNA_REGULACJA_OBROTOW_SPREZARKI")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "PRZEPLYW_POMPY_P0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OBROTY_WENTYLATORA_W0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OBROTY_SPREZARKI")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "SPRAWDZANIE_KOMUNIKACJI_Z_WENTYTLATOREM")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "STEROWANIE_WENTYLATORA_Z_EMERSONA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MOC_MAKSYMALNA_FAST_DLA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MOC_MAKSYMALNA_NORMAL_DLA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MOC_MAKSYMALNA_ECONO_DLA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OPOZNIENIE_ZALACZANIA_WENTYLATORA_PO_DEFROSCIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MINIMALNE_PRZEGRZANIE_DLA_DEFROSTU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "HISTEREZA_MINIMALNEGO_PRZEGRZANIA_DLA_DEFROSTU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "OPOZNIENIE_WYLACZENIA_ELEKTROZAWORU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_OCHRONY_SKRAPLACZA_DEFROST_MIN10C")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "TEMPERATURA_OCHRONY_SKRAPLACZA_DEFROST_PLUS3C")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "HISTEREZA_TEMPERATURY_OCHRONY_SKRAPLACZA_DEFROST")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "CZAS_DETEKCJI_ZMIANY_TEMPERATURY_DEFROST")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MAKSYMALNE_OBROTY_SPREZARKI_DLA_GRZANIA_I_CHLODZENIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "MAKSYMALNE_OBROTY_SPREZARKI_DLA_DEFROSTU")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRZYGOTOWANIE_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "ZAW_MIESZAJACY_OB1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_PV_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBECNA_MOC_GRZALEK_STATUS")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "work-parameters",
    name: "modules.menu.work_parameters",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.work_parameters",
      icon: a.CONFIGURATION,
      permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS
    },
    children: [{
      path: "pa-1",
      name: "modules.menu.pa_1",
      meta: {
        displayName: "routes.modules.menu.pa_1",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OBECNA_MOC_GRZALEK_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_A2_T2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZASILANIA_A2_T1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_POWROTU_A2_T7_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZAS_PRZED_GRZALKA_A1_T1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZAS_ZA_GRZALKA_A1_T4_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_POWROTU_A1_T3_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_SSANIA_A2_T3_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_SSANIA_PRZED_SPR_A2_T4_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_CIEKLEGO_CZYNNIKA_A2_T5_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ROZLADOWANIA_A2_DLT_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_PAROWANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_KONDENSACJI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEGRZANIE_TRYB_GRZANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEGRZANIE_SPR_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "DEFROST_I_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_PID_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "AKTUALNA_MOC_GRZANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_CHLODZENIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MAKS_DOSTEPNA_MOC_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MIN_DOSTEPNA_MOC_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OBROTY_SPREZARKI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PREDKOSC_MIN_SPREZARKI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PREDKOSC_MAKS_SPREZARKI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ZADANE_OBROTY_WENTYLATORA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "AKTUALNE_OBROTY_WENTYLATORA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "COP_GRZANIE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "COP_CHLODZENIE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CISNIENIE_SSANIA_P1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CISNIENIE_ROZLADOWANIA_P2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OTWARCIE_ZAWORU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OTWARCIE_ZAWORU_2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ODCZYT_PWM_P0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEPLYW_OBIEGU_CO0_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "AKTUALNA_TARYFA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "POZA_TARYFA")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-2",
      name: "modules.menu.pa_2",
      meta: {
        displayName: "routes.modules.menu.pa_2",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_2,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "REWIZJA_WEWNETRZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CISNIENIE_SSANIA_P1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CISNIENIE_ROZLADOWANIA_P2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_SSANIA_PRZED_SPR_A2_T4_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_CIEKLEGO_CZYNNIKA_A2_T5_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_ROZLADOWANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_POWROTU_A2_T7_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_ZASILANIA_A2_T1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "AKTUALNA_TARYFA_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-3",
      name: "modules.menu.pa_3",
      meta: {
        displayName: "routes.modules.menu.pa_3",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_3,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_OTOCZENIA_A2_T2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_SSANIA_A2_T3_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WEJSCIA_CYFROWE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WYJSCIA_CYFROWE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OTWARCIE_ZAWORU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OTWARCIE_ZAWORU_2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEGRZANIE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "NASTAWA_PRZEGRZANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "NASTAWA_PRZEGRZANIA_SPREZARKI_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-4",
      name: "modules.menu.pa_4",
      meta: {
        displayName: "routes.modules.menu.pa_4",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_4,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OBROTY_SPREZARKI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_PAROWANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZEGRZANIE_SPR_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "T_KONDENSACJI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ALARM_1_ALARMY_PROGRAMOWE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ALARM_2_ALARMY_PROGRAMOWE_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ALARM_SPRZETOWY_1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ALARM_SPRZETOWY_2_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-5",
      name: "modules.menu.pa_5",
      meta: {
        displayName: "routes.modules.menu.pa_5",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_5,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ALARM_1_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ALARM_2_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ALARM_SPRZETOWY_1_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ALARM_SPRZETOWY_2_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TEMPERATURA_GAZOW_WYLOTOWYCH_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_PRAD_WYJSCIOWY_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_OGRANICZENIE_PRADU_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-6",
      name: "modules.menu.pa_6",
      meta: {
        displayName: "routes.modules.menu.pa_6",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_6,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_PRAD_FAZOWY_SILNIKA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_NAPIECIE_SZYNY_DC_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_NAPIECIE_SIECI_AC_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_PRAD_LINII_AC_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_STATUS_SPADKU_PREDKOSCI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_TEMPERATURA_PLYTY_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_TEMPERATURA_IPM_MODULU_PRZETWORNICY_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_TEMPERATURA_IPM_MODULU_PFC_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-7",
      name: "modules.menu.pa_7",
      meta: {
        displayName: "routes.modules.menu.pa_7",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_7,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_TEMPERATURA_SILNIKA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_1_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_2_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WYDAJNOSC_GRZEWCZA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ZAPOTRZEBOWANIE_NA_MOC_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_CHLODZENIA_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-8",
      name: "modules.menu.pa_8",
      meta: {
        displayName: "routes.modules.menu.pa_8",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_8,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_TEMPERATURA_SILNIKA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_1_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_2_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WYDAJNOSC_GRZEWCZA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ZAPOTRZEBOWANIE_NA_MOC_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_CHLODZENIA_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-9",
      name: "modules.menu.pa_9",
      meta: {
        displayName: "routes.modules.menu.pa_9",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_9,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PWM_1_CZESTOTLIWOSC_SPRZEZENIA_ZWROTNEGO_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PWM_1_CYKL_PRACY_SPRZEZENIA_ZWROTNEGO_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PWM_2_CZESTOTLIWOSC_SPRZEZENIA_ZWROTNEGO_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PWM_2_CYKL_PRACY_SPRZEZENIA_ZWROTNEGO_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "STAN_CHLODZENIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "STABILNOSC_PRZEGRZANIA_PRZY_CHLODZENIU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CHLODZENIE_PID_KP_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CHLODZENIE_PID_KI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CHLODZENIE_PID_KD_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-10",
      name: "modules.menu.pa_10",
      meta: {
        displayName: "routes.modules.menu.pa_10",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_10,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OBROTY_MIERZONE_WENTYLATORA_1_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "STAN_REGULACJI_PREDKOSCI_OBROTOWEJ_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OBROTY_MIERZONE_WENTYLATORA_2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "SEER_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "DEFROST_I_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MOC_GRZALKI_STOJANA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PREDKOSC_WENTYLATORA_1_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-11",
      name: "modules.menu.pa_11",
      meta: {
        displayName: "routes.modules.menu.pa_11",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_11,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MINIMALNE_OBROTY_SPREZARKI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PREDKOSC_MAKS_SPREZARKI_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_3_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_4_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_3_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_4_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZYCZYNA_ODSZRANIANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PRZYCZYNA_RESETOWANIA_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-12",
      name: "modules.menu.pa_12",
      meta: {
        displayName: "routes.modules.menu.pa_12",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_12,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ILOSC_STARTOW_SPREZARKI_W_CIAGU_OSTATNIEJ_GODZINY_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WERSJA_EEPROM_NAPEDU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ZMIANA_PARAMEROW_DOMYSLNYCH_NAPEDU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "NAPED_DSP_WERSJA_GLOWNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "NAPED_DSP_WERSJA_TESTOWA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "STAN_NAPEDU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MAKS_DOSTEPNA_MOC_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "MIN_DOSTEPNA_MOC_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-13",
      name: "modules.menu.pa_13",
      meta: {
        displayName: "routes.modules.menu.pa_13",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_13,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ENERGIA_GRZANIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "OGRZEWANIE_ENERGIA_ELEKTRYCZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ENERGIA_CHLODZENIA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CHLODZENIE_ENERGIA_ELEKTRYCZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "CHLODZENIE_ENERGIA_ELEKTRYCZNA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "ZEGAR_SYSTEMOWY_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-14",
      name: "modules.menu.pa_14",
      meta: {
        displayName: "routes.modules.menu.pa_14",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_14,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "TREND_SIGMA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WERSJA_BOOTLOADERA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "PREDKOSC_WENTYLATORA_2_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_NUMER_MODELU_NAPEDU_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_NUMER_MODELU_KOMPRESORA_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-15",
      name: "modules.menu.pa_15",
      meta: {
        displayName: "routes.modules.menu.pa_15",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_15,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_MODEL_TERMISTORA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "SZACUNKOWA_TEMPERATURA_PRZEWODU_ODPROWADZAJACEGO_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WERSJA_BOOTLOADERA_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_AWARIE_KOMUNIKACJI_MODBUS_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_STATUS_KOMUNIKACJI_MODBUS_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_5_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_BLAD_WYLACZENIA_5_CIEN_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "VSS_LIMIT_DLT_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pa-16",
      name: "modules.menu.pa_16",
      meta: {
        displayName: "routes.modules.menu.pa_16",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_MENU_WORK_PARAMETERS_PA_16,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "STAN_PRZELACZNIKOW_DIP_READ")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
            parameter: e(E.READ, "WSKAZNIK_WLASCIWOSCI_PAROWNIKA_PRZY_AKTUALNEJ_PREDKOSCI_OBROTOWEJ_READ")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }]
  }, {
    path: "lock-board",
    name: "modules.menu.lock_board",
    meta: {
      displayName: "routes.modules.menu.lock_board",
      icon: a.CHECKLIST,
      permissionModule: A.DISPLAY_MENU_LOCK_BOARD,
      parameters: {
        read: [],
        write: [],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_MALY_PRZEPLYW")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_BLAD_OBCEGO_PRZEPLYWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_POZA_TARYFA_OBNIZENIE_NIEAKTYWNE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_ZA_MALA_POTRZEBNA_MOC")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_TRYB_LATO_BRAK_GRZANIA_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_BLOKADA_SPREZARKI_W_MENU_KONFIGURACJI")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_AKTYWNE_ODPOWIETRZANIE_OBIEGU_CO0_LUB_CWU")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_AKTYWNE_ODPOWIETRZANIE_OBIEGU_CO1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_BLAD_CZUJNIKA_TEMPERATURY_A2_T1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_BLAD_CZUJNIKA_TEMPERATURY_A2_T1_TZS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_TEMPERATURA_WODY_ZA_SKRAPLACZEM_NIZSZA_NIZ_SKR_TZS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_TEMPERATURA_WODY_ZA_SKRAPLACZEM_NIZSZA_NIZ_SKR_T1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_POMPA_CIEPLA_WYLACZONA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TEMPERATURA_WODY_JEST_NIZSZA_NIZ_MINIMALNA_DLA_CHLODZENIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "SG_READY_TRYB1_BLOKADA_OPERATORA_SIECI")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_OPOZNIENIE_PRZELACZANIA_CHLODZENIE_GRZANIE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_SPREZARKI_PRZEZ_TERMOSTATY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_PODGRZEWANIE_KARTERU_SPREZARKI")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "BLOKADA_1_GLOBALNY_STAN_BLOKADY")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "schema",
    name: "modules.menu.schema",
    meta: {
      displayName: "routes.modules.menu.schema",
      icon: a.SITEMAP,
      permissionModule: A.DISPLAY_MENU_SCHEMA,
      parameters: {
        read: [],
        write: [],
        status: [],
        special: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "OBECNA_MOC_GRZALEK_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ZEWNETRZNA_SREDNIA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_WEW_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_WEW_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "ZADANA_TEMP_CO0_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.WRITE, "ZADANA_TEMP_CO1_WRITE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_WYLICZANA_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_WYLICZANA_CO1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMPERATURA_A1_T4")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMPERATURA_A1_T10")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "OBIEG_CO1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMPERATURA_A1_T1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "TRYB_PRACY_CWU_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMPERATURA_A1_T7")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMPERATURA_A1_T3")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P0_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_ZAWORU_M0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_CALKOWITY")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "PRACA_POMPY_P1_STATUS")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_ZAWORU_M1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEPLYW_IPWM_P1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "TEMP_OBIEGU_CO0_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_POWROTU_A2_T7_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_CIEKLEGO_CZYNNIKA_A2_T5_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_OTOCZENIA_A2_T2_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "DEFROST_I_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_SSANIA_A2_T3_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_SSANIA_PRZED_SPR_A2_T4_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "OTWARCIE_ZAWORU_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "ZADANE_OBROTY_WENTYLATORA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_ZAWORU_4D")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "OBROTY_SPREZARKI_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "CISNIENIE_ROZLADOWANIA_P2_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "CISNIENIE_SSANIA_P1_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_PAROWANIA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_KONDENSACJI_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PRZEGRZANIE_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "T_ROZLADOWANIA_A2_DLT_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "MOC_PID_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "AKTUALNA_MOC_GRZANIA_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "COP_GRZANIE_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "COP_CHLODZENIE_READ")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.STATUS, "STATUS_POMPY_CIEPLA_STATUS")
        }]
      }
    },
    component: M.SchemaView
  }, {
    path: "boiler",
    name: "modules.menu.boiler",
    meta: {
      displayName: "routes.modules.menu.boiler",
      icon: a.BOILER,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_4")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_8")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "URUCHOMIENIE_KOTLA")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_66")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_13")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_7")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_9")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_12")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_8")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_176")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_10")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_407")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_11")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "boiler/reserve",
    name: "modules.menu.boilerReserve",
    meta: {
      displayName: "routes.modules.menu.boilerReserve",
      icon: a.BOILER,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_363")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_81")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "boiler/blower",
    name: "modules.menu.blower",
    meta: {
      displayName: "routes.modules.menu.blower",
      icon: a.FAN,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_49")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_15")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_6")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_5")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_3")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_4")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_360")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_26")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_365")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_366")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_22")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_23")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_24")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_25")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_10")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_18")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_27")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_76")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_10")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "boiler/blower/2",
    name: "modules.menu.blower2",
    meta: {
      displayName: "routes.modules.menu.blower2",
      icon: a.FAN2,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_214")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_213")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_372")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_215")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_208")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_294")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_293")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_41")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "boiler/burner",
    name: "modules.menu.burner",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.burner",
      icon: a.BURNER,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1
    },
    children: [{
      path: "status",
      name: "modules.menu.burnerPreview",
      meta: {
        displayName: "routes.modules.menu.burnerPreview",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_13")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_43")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_14")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_56")
          }],
          write: [],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "",
      name: "modules.menu.burnerSettings",
      meta: {
        displayName: "routes.modules.menu.burnerSettings",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_9")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_36")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_171")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_6")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_73")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_23")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_24")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_25")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "ignition",
      name: "modules.menu.burnerIgnition",
      meta: {
        displayName: "routes.modules.menu.burnerIgnition",
        icon: a.FIRE,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_136")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_138")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_139")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_140")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_141")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_142")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_143")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_137")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_135")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "work",
      name: "modules.menu.burnerWork",
      meta: {
        displayName: "routes.modules.menu.burnerWork",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_149")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_148")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_156")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_167")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_168")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "sustain",
      name: "modules.menu.burnerSustain",
      meta: {
        displayName: "routes.modules.menu.burnerSustain",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_158")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_169")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_159")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "cleaning",
      name: "modules.menu.burnerCleaning",
      meta: {
        displayName: "routes.modules.menu.burnerCleaning",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_155")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_166")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_144")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_145")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_146")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_147")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "damping",
      name: "modules.menu.burnerDamping",
      meta: {
        displayName: "routes.modules.menu.burnerDamping",
        icon: a.CONFIGURATION,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_160")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_161")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_163")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }]
  }, {
    path: "boiler/feeder",
    name: "modules.menu.feeder",
    meta: {
      displayName: "routes.modules.menu.feeder",
      icon: a.FEEDER,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_59")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_3")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_61")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_2")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_3")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_4")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_5")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_11")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_12")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_13")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_14")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_21")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_19")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_15")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_16")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_65")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_17")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_35")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_181")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_20")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_183")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_180")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_64")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_29")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_13")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "boiler/return",
    name: "modules.menu.return",
    meta: {
      displayName: "routes.modules.menu.return",
      icon: a.RETURN,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_1")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_398")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_12")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "buffer",
    name: "modules.menu.buffer",
    meta: {
      displayName: "routes.modules.menu.buffer",
      icon: a.BUFFER,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_6")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_30")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_303")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_240")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_392")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_69")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_68")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_304")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_67")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_239")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_23")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "boiler/dhw",
    name: "modules.menu.boilerDHW",
    meta: {
      displayName: "routes.modules.menu.boilerDHW",
      icon: a.FAUCET,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_2")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_51")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_50")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_277")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_48")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_49")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_190")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_173")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_174")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_394")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_46")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_47")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_19")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "circulation",
    name: "modules.menu.circulation",
    meta: {
      displayName: "routes.modules.menu.circulation",
      icon: a.CIRCULATION,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_217")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_218")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_273")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.STATUS, "STATUS_P5_49")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "boiler/exhaust-gas",
    name: "modules.menu.exhaustGas",
    meta: {
      displayName: "routes.modules.menu.exhaustGas",
      icon: a.EXHAUST_GAS,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_7")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_16")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_51")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_52")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_53")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_54")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_55")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_20")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_350")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_347")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_348")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_349")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_384")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_19")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_26")
        }],
        status: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_269")
        }],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "timezones",
    name: "modules.menu.timeZones.settings",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.timeZones.settings",
      icon: a.SCHEDULES,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [],
        write: [],
        status: [],
        special: []
      }
    },
    children: wA
  }, {
    path: "thermostats",
    name: "modules.menu.thermostats",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.thermostats",
      icon: a.THERMOSTAT,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1
    },
    children: [{
      path: "pump",
      name: "modules.menu.thermostat.pump",
      meta: {
        displayName: "routes.modules.menu.thermostat.pump",
        icon: a.THERMOSTAT,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P17_0")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_31")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_30")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_391")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_0")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_1")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_2")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_3")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_4")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_5")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_6")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_7")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_8")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_9")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_12")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_13")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_32")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_14")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "pump/additional",
      name: "modules.menu.thermostat.pumpAdditional",
      meta: {
        displayName: "routes.modules.menu.thermostat.pumpAdditional",
        icon: a.THERMOSTAT,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P17_12")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_84")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_85")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_86")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_87")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_88")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_89")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_90")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_91")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_92")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_93")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_96")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_97")
          }],
          status: [],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/1",
      name: "modules.menu.thermostat.valve1",
      meta: {
        displayName: "routes.modules.menu.thermostat.valve1",
        icon: a.THERMOSTAT,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P17_2")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_62")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_63")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_14")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_15")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_16")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_17")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_18")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_19")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_20")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_21")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_22")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_23")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_26")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_27")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_61")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_22")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/1_2",
      name: "modules.menu.thermostat.valve1_2",
      meta: {
        displayName: "routes.modules.menu.thermostat.valve1_2",
        icon: a.THERMOSTAT,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P17_35")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_315")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_316")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_98")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_99")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_100")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_101")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_102")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_103")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_104")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_105")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_106")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_107")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_110")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_111")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_314")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_53")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/2",
      name: "modules.menu.thermostat.valve2",
      meta: {
        displayName: "routes.modules.menu.thermostat.valve2",
        icon: a.THERMOSTAT,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P17_4")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_89")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_90")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_28")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_29")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_30")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_31")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_32")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_33")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_34")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_35")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_36")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_37")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_40")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_41")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_88")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_27")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/3",
      name: "modules.menu.thermostat.valve3",
      meta: {
        displayName: "routes.modules.menu.thermostat.valve3",
        icon: a.THERMOSTAT,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P17_6")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_101")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_102")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_42")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_43")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_44")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_45")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_46")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_47")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_48")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_49")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_50")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_51")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_54")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_55")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_100")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_30")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/4",
      name: "modules.menu.thermostat.valve4",
      meta: {
        displayName: "routes.modules.menu.thermostat.valve4",
        icon: a.THERMOSTAT,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P17_8")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_113")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_114")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_56")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_57")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_58")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_59")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_60")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_61")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_62")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_63")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_64")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_65")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_68")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_69")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_112")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_33")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/5",
      name: "modules.menu.thermostat.valve5",
      meta: {
        displayName: "routes.modules.menu.thermostat.valve5",
        icon: a.THERMOSTAT,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P17_10")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_125")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_126")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_70")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_71")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_72")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_73")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_74")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_75")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_76")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_77")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_78")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_79")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_82")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_P16_83")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_124")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_36")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }]
  }, {
    path: "valves",
    name: "modules.menu.valves",
    meta: {
      displayDropdown: !0,
      displayName: "routes.modules.menu.valves",
      icon: a.VALVE,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1
    },
    children: [{
      path: "valve/1",
      name: "modules.menu.valve1",
      meta: {
        displayName: "routes.modules.menu.valve1",
        icon: a.VALVE,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_5")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_52")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_54_55_56")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_54")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_55")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_56")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_53")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_59")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_60")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_58")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_57")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_408")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_21")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_20")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/1_2",
      name: "modules.menu.valve1_2",
      meta: {
        displayName: "routes.modules.menu.valve1_2",
        icon: a.VALVE,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_46")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_305")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_307_308_309")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_307")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_308")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_309")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_306")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_312")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_313")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_311")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_310")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_440")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_52")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_51")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/2",
      name: "modules.menu.valve2",
      meta: {
        displayName: "routes.modules.menu.valve2",
        icon: a.VALVE,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_9")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_79")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_81_82_83")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_81")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_82")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_83")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_80")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_86")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_87")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_85")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_84")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_26")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_25")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/3",
      name: "modules.menu.valve3",
      meta: {
        displayName: "routes.modules.menu.valve3",
        icon: a.VALVE,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_10")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_91")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_93_94_95")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_93")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_94")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_95")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_92")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_98")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_99")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_97")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_96")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_29")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_28")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/4",
      name: "modules.menu.valve4",
      meta: {
        displayName: "routes.modules.menu.valve4",
        icon: a.VALVE,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_11")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_103")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_105_106_107")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_105")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_106")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_107")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_104")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_110")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_111")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_109")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_108")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_32")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_31")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }, {
      path: "valve/5",
      name: "modules.menu.valve5",
      meta: {
        displayName: "routes.modules.menu.valve5",
        icon: a.VALVE,
        permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
        parameters: {
          read: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.READ, "PARAM_P4_12")
          }],
          write: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_115")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_117_118_119")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_117")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_118")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_119")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_116")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_122")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_123")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_121")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.WRITE, "PARAM_120")
          }],
          status: [{
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_35")
          }, {
            permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
            parameter: e(E.STATUS, "STATUS_P5_34")
          }],
          special: []
        }
      },
      component: M.ParametersView
    }]
  }, {
    path: "about",
    name: "modules.menu.about",
    meta: {
      displayName: "routes.modules.menu.about",
      icon: a.INFO,
      permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_2")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_3")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_4")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_5")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_6")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_7")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_8")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_9")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_10")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_11")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_12")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_13")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_14")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_15")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_16")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_17")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_18")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_19")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_20")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_21")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P11_22")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "COMMAND_MODULE_RESTART")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_186")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_P8_0")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_P8_1")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_P8_2")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_P8_3")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_P8_4")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_P8_5")
        }],
        status: [],
        special: []
      }
    },
    component: M.ParametersView
  }, {
    path: "dev",
    name: "modules.menu.dev",
    meta: {
      displayName: "routes.modules.menu.dev",
      icon: a.DEV_TO,
      permissionModule: A.DISPLAY_MENU_DEV,
      parameters: {
        read: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_DISPLAY_SERVICER_CODE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_MAX,
          parameter: e(E.READ, "PARAM_DISPLAY_PRODUCER_CODE")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_17")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_18")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_19")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_20")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_21")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_22")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_23")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_24")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_25")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_26")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_27")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_28")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_29")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_31")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_32")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_33")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_34")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_35")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_36")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_37")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_38")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_39")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_40")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_41")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_42")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_45")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_47")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_48")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_50")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_57")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_58")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_63")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_P4_64")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.READ, "PARAM_71")
        }],
        write: [{
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_P8_0_DEV")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_443")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_449")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_450")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_452")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_453")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_2")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_11")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_14")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_28")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_33")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_34")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_37")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_38")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_39")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_40")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_41")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_42")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_43")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_44")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_45")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_70")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_71")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_72")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_74")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_75")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_77")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_78")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_127")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_128")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_129")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_130")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_131")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_132")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_133")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_134")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_150")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_151")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_152")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_153")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_154")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_157")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_162")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_164")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_165")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_170")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_172")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_175")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_182")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_184")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_185")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_187")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_188")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_189")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_191")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_192")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_193")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_194")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_195")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_196")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_197")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_198")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_203")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_204")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_205")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_206")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_207")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_209")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_210")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_211")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_212")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_216")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_220")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_221")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_222")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_223")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_224")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_225")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_226")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_227")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_228")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_229")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_230")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_231")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_232")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_233")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_234")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_235")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_236")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_237")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_238")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_241")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_242")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_243")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_244")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_245")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_246")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_247")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_248")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_249")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_250")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_251")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_252")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_253")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_254")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_255")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_256")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_257")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_258")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_259")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_260")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_261")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_262")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_263")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_264")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_265")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_266")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_267")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_268")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_270")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_271")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_272")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_274")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_275")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_276")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_278")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_279")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_280")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_281")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_282")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_283")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_284")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_285")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_286")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_287")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_288")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_289")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_290")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_291")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_292")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_295")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_296")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_297")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_298")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_299")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_300")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_301")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_302")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_317")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_318")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_319")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_320")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_321")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_322")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_323")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_324")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_325")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_326")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_327")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_328")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_329")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_330")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_331")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_332")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_333")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_334")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_335")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_336")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_337")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_338")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_339")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_340")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_341")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_342")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_343")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_344")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_345")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_346")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_351")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_352")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_353")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_354")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_355")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_356")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_357")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_358")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_359")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_361")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_362")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_364")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_367")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_368")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_369")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_370")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_371")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_373")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_374")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_375")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_376")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_377")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_378")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_379")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_380")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_381")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_382")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_383")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_385")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_386")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_387")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_388")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_389")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_393")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_395")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_396")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_397")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_399")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_400")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_401")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_402")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_403")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_404")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_405")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_406")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_409")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_410")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_411")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_412")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_413")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_414")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_415")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_416")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_417")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_418")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_419")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_420")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_421")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_422")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_423")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_424")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_425")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_426")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_427")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_428")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_429")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_430")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_431")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_432")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_433")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_434")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_435")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_437")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_438")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM_439")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_6")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_7")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_8")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_9")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_10")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_15")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_16")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_17")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_18")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_21")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_22")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_23")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_24")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_30")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_25")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_27")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_28")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_29")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_31")
        }, {
          permissionModule: A.DISPLAY_PARAMETER_LEVEL_1,
          parameter: e(E.WRITE, "PARAM16_32")
        }],
        status: [],
        special: []
      }
    },
    component: M.ParametersView
  }],
  Ee = {
    deviceMenu: zA
  };
export {
  Ee as default
};
