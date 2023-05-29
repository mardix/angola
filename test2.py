from angola import lib, lib_xql


{
    "_created_at:$BETWEEN": ["[[@:UUID()]]", "[[@:NOW()]]"]
}
r = lib_xql.eval_macros(["[[@MACRO:NOW, +3hours, YYYY-MM-DD HH:mm:ss]]", "[[@:NOW()]]", "[[@MACRO:UUID()]]"])
r = lib_xql.eval_macros("[[@MACRO:NOW, +5days, YYYY-MM-DD]]")
r = lib_xql.eval_macros("[[@MACRO:NOW,,YYYY-MM-DD]]")

print("R", r)

"[[@MACRO:NOW, +2DAYS, YYYY-MM-DD]]"
b = ["[[@MACRO:NOW]]"]

{
    "_date:$GT": "[[@MACRO:NOW, -2Days]]"
}