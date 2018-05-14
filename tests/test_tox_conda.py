def test_skip_unknown_interpreter_result_json(cmd, initproj):
    initproj("conda-01", filedefs={
        'tox.ini': '''
            [tox]
            envlist=py27,
            [testenv]
            deps =
              itsdangerous
        '''
    })
    result = cmd()
    assert not result.ret
    assert "congratulations" in result.out
