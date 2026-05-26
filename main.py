@app.get("/teste")
async def teste():
    return {"status": "funcionando"}
